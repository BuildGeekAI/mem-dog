# Deploying mem-dog on AWS (EKS)

Production deployment on Amazon Elastic Kubernetes Service with optional Fargate for the UI.

```mermaid
graph TD
    subgraph Fargate ["AWS Fargate (optional)"]
        UI[UI · Next.js]
    end

    subgraph EKS ["EKS Cluster"]
        ALB[ALB Ingress Controller]
        subgraph ns_memdog ["namespace: mem-dog"]
            API[API · FastAPI]
            MCP[MCP Server · SSE]
        end
        subgraph ns_pipeline ["namespace: webhook-pipeline"]
            NATS[NATS JetStream]
            AGENTS[40 AI Agents]
            OLLAMA[Ollama · 4b/12b/27b]
        end
        subgraph ns_gateway ["namespace: webhook-gateway"]
            WGW[Webhook Gateway]
        end
        subgraph ns_data ["namespace: data"]
            PG[(Postgres + pgvector)]
            NEO[(Neo4j)]
        end
    end

    subgraph Storage ["AWS Services"]
        ECR[ECR · Container Registry]
        S3[(S3 · raw binary)]
        RDS[(RDS PostgreSQL · optional)]
    end

    UI --> ALB
    ALB --> API
    ALB --> MCP
    ALB --> WGW
    AGENTS --> API
    API --> PG
    API --> S3
    API --> NEO
```

---

## Prerequisites

### Tools

```bash
# macOS
brew install awscli eksctl docker
brew install node@20 jq
curl -LsSf https://astral.sh/uv/install.sh | sh

# Linux
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip
unzip awscliv2.zip && sudo ./aws/install
curl -sLO "https://github.com/eksctl-io/eksctl/releases/latest/download/eksctl_Linux_amd64.tar.gz"
tar xz -C /usr/local/bin -f eksctl_Linux_amd64.tar.gz
```

### Authenticate

```bash
aws configure
# Region: us-east-1 (or your preference)
# Output: json
```

---

## Step 1 — Create ECR Repositories

```bash
REGION=us-east-1
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_BASE=$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com

aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_BASE

for repo in api mcp-server webhook-gateway webhook-receiver webhook-agent ui; do
  aws ecr create-repository --repository-name mem-dog/$repo --region $REGION 2>/dev/null
done
```

---

## Step 2 — Create EKS Cluster

```bash
eksctl create cluster \
  --name mem-dog \
  --region $REGION \
  --nodegroup-name workers \
  --node-type t3.xlarge \
  --nodes 3 \
  --nodes-min 2 \
  --nodes-max 5 \
  --managed

kubectl get nodes  # verify
```

### Recommended Node Sizing

| Workload | Instance Type | Nodes | Notes |
|----------|--------------|-------|-------|
| Dev/test | t3.xlarge (4 vCPU, 16 GB) | 3 | Sufficient for all services |
| Production | m5.2xlarge (8 vCPU, 32 GB) | 3-5 | Headroom for Ollama |
| GPU | g4dn.xlarge (T4 GPU) | 1 | Add via separate node group |

### Install AWS Load Balancer Controller

```bash
# IAM policy for the controller
curl -o iam_policy.json https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v2.7.1/docs/install/iam_policy.json

aws iam create-policy \
  --policy-name AWSLoadBalancerControllerIAMPolicy \
  --policy-document file://iam_policy.json

# Service account
eksctl create iamserviceaccount \
  --cluster=mem-dog \
  --namespace=kube-system \
  --name=aws-load-balancer-controller \
  --attach-policy-arn=arn:aws:iam::$ACCOUNT_ID:policy/AWSLoadBalancerControllerIAMPolicy \
  --approve

# Install via Helm
helm repo add eks https://aws.github.io/eks-charts
helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=mem-dog \
  --set serviceAccount.create=false \
  --set serviceAccount.name=aws-load-balancer-controller
```

---

## Step 3 — Build and Push Images

```bash
# API
docker build --platform linux/amd64 -t $ECR_BASE/mem-dog/api:latest api/
docker push $ECR_BASE/mem-dog/api:latest

# MCP Server
docker build --platform linux/amd64 -t $ECR_BASE/mem-dog/mcp-server:latest -f mcp-server/Dockerfile .
docker push $ECR_BASE/mem-dog/mcp-server:latest

# Webhook Gateway
docker build --platform linux/amd64 -t $ECR_BASE/mem-dog/webhook-gateway:latest webhook-gateway/
docker push $ECR_BASE/mem-dog/webhook-gateway:latest

# Webhook Receiver
docker build --platform linux/amd64 -t $ECR_BASE/mem-dog/webhook-receiver:latest -f webhook/receiver/Dockerfile webhook/receiver/
docker push $ECR_BASE/mem-dog/webhook-receiver:latest

# Webhook Agent
docker build --platform linux/amd64 -t $ECR_BASE/mem-dog/webhook-agent:latest -f webhook/processor/Dockerfile webhook/processor/
docker push $ECR_BASE/mem-dog/webhook-agent:latest

# UI
docker build --platform linux/amd64 -t $ECR_BASE/mem-dog/ui:latest ui/
docker push $ECR_BASE/mem-dog/ui:latest
```

---

## Step 4 — Deploy Data Layer

### Option A — RDS PostgreSQL (managed)

```bash
PG_PASSWORD=$(openssl rand -base64 24)

# Get VPC and subnets from EKS
VPC_ID=$(aws eks describe-cluster --name mem-dog --query "cluster.resourcesVpcConfig.vpcId" --output text)
SUBNET_IDS=$(aws eks describe-cluster --name mem-dog --query "cluster.resourcesVpcConfig.subnetIds" --output text)

# Create subnet group
aws rds create-db-subnet-group \
  --db-subnet-group-name mem-dog-db \
  --db-subnet-group-description "mem-dog RDS subnets" \
  --subnet-ids $SUBNET_IDS

# Get EKS security group
EKS_SG=$(aws eks describe-cluster --name mem-dog --query "cluster.resourcesVpcConfig.clusterSecurityGroupId" --output text)

# Create RDS instance
aws rds create-db-instance \
  --db-instance-identifier mem-dog-pg \
  --db-instance-class db.t3.medium \
  --engine postgres \
  --engine-version 16 \
  --master-username memdog \
  --master-user-password "$PG_PASSWORD" \
  --allocated-storage 20 \
  --db-subnet-group-name mem-dog-db \
  --vpc-security-group-ids $EKS_SG \
  --no-publicly-accessible

# Wait for it to be available
aws rds wait db-instance-available --db-instance-identifier mem-dog-pg

# Get endpoint
RDS_ENDPOINT=$(aws rds describe-db-instances --db-instance-identifier mem-dog-pg \
  --query "DBInstances[0].Endpoint.Address" --output text)

POSTGRES_URL="postgresql://memdog:$PG_PASSWORD@$RDS_ENDPOINT:5432/memdog"

# Enable pgvector (connect and run)
# psql $POSTGRES_URL -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### Option B — In-cluster PostgreSQL

```bash
kubectl create namespace data

kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
  namespace: data
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
        - name: postgres
          image: pgvector/pgvector:pg16
          ports:
            - containerPort: 5432
          env:
            - name: POSTGRES_USER
              value: memdog
            - name: POSTGRES_PASSWORD
              value: memdog
            - name: POSTGRES_DB
              value: memdog
          volumeMounts:
            - name: pgdata
              mountPath: /var/lib/postgresql/data
      volumes:
        - name: pgdata
          persistentVolumeClaim:
            claimName: pgdata
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: pgdata
  namespace: data
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: gp3
  resources:
    requests:
      storage: 20Gi
---
apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: data
spec:
  selector:
    app: postgres
  ports:
    - port: 5432
EOF

POSTGRES_URL="postgresql://memdog:memdog@postgres.data.svc.cluster.local:5432/memdog"
```

### Neo4j (in-cluster)

```bash
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: neo4j
  namespace: data
spec:
  replicas: 1
  selector:
    matchLabels:
      app: neo4j
  template:
    metadata:
      labels:
        app: neo4j
    spec:
      containers:
        - name: neo4j
          image: neo4j:5.26-community
          ports:
            - containerPort: 7687
            - containerPort: 7474
          env:
            - name: NEO4J_AUTH
              value: neo4j/memdog_neo4j
            - name: NEO4J_PLUGINS
              value: '["apoc"]'
          volumeMounts:
            - name: neo4j-data
              mountPath: /data
      volumes:
        - name: neo4j-data
          persistentVolumeClaim:
            claimName: neo4j-data
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: neo4j-data
  namespace: data
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: gp3
  resources:
    requests:
      storage: 10Gi
---
apiVersion: v1
kind: Service
metadata:
  name: neo4j
  namespace: data
spec:
  selector:
    app: neo4j
  ports:
    - name: bolt
      port: 7687
    - name: http
      port: 7474
EOF
```

---

## Step 5 — Deploy Application

### Create namespaces and config

```bash
kubectl create namespace mem-dog
kubectl create namespace webhook-pipeline
kubectl create namespace webhook-gateway
```

### API

```bash
kubectl -n mem-dog create configmap api-config \
  --from-literal=STORAGE_BACKEND=local \
  --from-literal=POSTGRES_URL="$POSTGRES_URL" \
  --from-literal=NEO4J_URI="bolt://neo4j.data.svc.cluster.local:7687" \
  --from-literal=NEO4J_USER=neo4j \
  --from-literal=NEO4J_PASSWORD=memdog_neo4j \
  --from-literal=ENVIRONMENT=dev

sed "s|image: mem-dog-api|image: $ECR_BASE/mem-dog/api:latest|" \
  k8s/api-deployment.yaml | kubectl apply -f -
kubectl apply -f k8s/api-service.yaml 2>/dev/null || \
  kubectl expose deployment api -n mem-dog --port=8080 --type=ClusterIP
```

### MCP Server

```bash
kubectl -n mem-dog create configmap mcp-server-config \
  --from-literal=MEM_DOG_API_URL="http://api.mem-dog.svc.cluster.local:8080" \
  --from-literal=LOG_LEVEL=INFO \
  --from-literal=PORT=8080

sed "s|image: mcp-server:latest|image: $ECR_BASE/mem-dog/mcp-server:latest|" \
  k8s/mcp-server-deployment.yaml | kubectl apply -f -
kubectl apply -f k8s/mcp-server-service.yaml
```

### Webhook Gateway

```bash
kubectl -n webhook-gateway create configmap webhook-gateway-config \
  --from-literal=MEM_DOG_API_URL="http://api.mem-dog.svc.cluster.local:8080" \
  --from-literal=LLM_PROVIDER=gemini \
  --from-literal=LOG_LEVEL=INFO

kubectl -n webhook-gateway create secret generic webhook-gateway-secrets \
  --from-literal=GEMINI_API_KEY="<your-key>"

sed "s|image: webhook-gateway:latest|image: $ECR_BASE/mem-dog/webhook-gateway:latest|" \
  k8s/webhook-gateway/deployment.yaml | kubectl apply -f -
kubectl apply -f k8s/webhook-gateway/service.yaml
```

### ALB Ingress

```bash
kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: mem-dog-ingress
  namespace: mem-dog
  annotations:
    kubernetes.io/ingress.class: alb
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/listen-ports: '[{"HTTP": 80}]'
spec:
  rules:
    - http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: api
                port:
                  number: 8080
          - path: /mcp
            pathType: Prefix
            backend:
              service:
                name: mcp-server
                port:
                  number: 8080
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: webhook-ingress
  namespace: webhook-gateway
  annotations:
    kubernetes.io/ingress.class: alb
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/group.name: mem-dog
spec:
  rules:
    - http:
        paths:
          - path: /webhooks
            pathType: Prefix
            backend:
              service:
                name: webhook-gateway
                port:
                  number: 8080
EOF

# Get ALB URL (takes 2-3 min to provision)
kubectl get ingress -n mem-dog mem-dog-ingress
```

---

## Step 6 — Deploy UI

### Option A — EKS (in-cluster)

```bash
sed "s|image: mem-dog-ui|image: $ECR_BASE/mem-dog/ui:latest|" \
  k8s/ui-deployment.yaml | kubectl apply -f -
```

### Option B — AWS App Runner

```bash
aws apprunner create-service \
  --service-name mem-dog-ui \
  --source-configuration '{
    "ImageRepository": {
      "ImageIdentifier": "'$ECR_BASE'/mem-dog/ui:latest",
      "ImageRepositoryType": "ECR",
      "ImageConfiguration": {
        "Port": "8080",
        "RuntimeEnvironmentVariables": {
          "API_URL": "http://<ALB_URL>/api"
        }
      }
    },
    "AutoDeploymentsEnabled": false,
    "AuthenticationConfiguration": {
      "AccessRoleArn": "arn:aws:iam::'$ACCOUNT_ID':role/AppRunnerECRAccess"
    }
  }'
```

---

## Step 7 — Verify

```bash
ALB_URL=$(kubectl get ingress -n mem-dog mem-dog-ingress \
  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')

curl http://$ALB_URL/api/health
curl http://$ALB_URL/mcp/health

kubectl get pods -n mem-dog
kubectl get pods -n webhook-pipeline
kubectl get pods -n webhook-gateway
kubectl get pods -n data
```

### Connect Claude Desktop

```json
{
  "mcpServers": {
    "mem-dog": {
      "url": "http://<ALB_URL>/mcp/sse",
      "headers": { "x-api-key": "md_your_key" }
    }
  }
}
```

---

## S3 for Raw Storage (optional)

Use S3 instead of local filesystem for binary data:

```bash
BUCKET=mem-dog-raw-data-$ACCOUNT_ID

aws s3 mb s3://$BUCKET --region $REGION

# Create IAM policy for S3 access
# Attach to EKS node role or use IRSA (IAM Roles for Service Accounts)

# Set on API configmap:
kubectl -n mem-dog set env deployment/api \
  STORAGE_BACKEND=gcs \
  RAW_BUCKET=$BUCKET
```

---

## TLS (optional)

```bash
# Request ACM certificate
aws acm request-certificate \
  --domain-name mem-dog.yourdomain.com \
  --validation-method DNS

# Add to ingress annotation:
#   alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:...
#   alb.ingress.kubernetes.io/listen-ports: '[{"HTTPS": 443}]'
#   alb.ingress.kubernetes.io/ssl-redirect: '443'
```

---

## Cost Estimate

| Resource | Monthly Cost |
|----------|-------------|
| EKS cluster (control plane) | ~$73 |
| EC2 nodes (3x t3.xlarge) | ~$150-200 |
| RDS PostgreSQL (db.t3.medium) | ~$50-65 |
| ALB | ~$20-30 |
| S3 + ECR | ~$5-10 |
| **Total** | **~$300-380/mo** |

Use in-cluster Postgres + Spot instances to reduce to ~$150-200/mo.
