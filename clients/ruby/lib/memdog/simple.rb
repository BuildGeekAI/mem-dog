# frozen_string_literal: true

require "date"

module MemDog
  # High-level 7-method facade. For full API coverage use MemDog::Client.
  class Simple
    attr_reader :client

    def initialize(base_url:, api_key: nil, user_id: nil, timeout: 30)
      @client  = Client.new(base_url: base_url, api_key: api_key, user_id: user_id, timeout: timeout)
      @user_id = user_id
    end

    def add(content: nil, file: nil, tags: nil, name: nil, description: nil,
            memory_type: nil, memory_id: nil, user_id: nil)
      data = @client.create_data(content: content, file: file, tags: tags, name: name,
                                  description: description, memory_ids: memory_id ? [memory_id] : nil)
      data_id = data["data_id"] || data["id"]
      result  = { "data_id" => data_id, "memory_id" => memory_id }

      if memory_type && !memory_id
        uid      = user_id || @user_id
        mem_name = "auto-#{memory_type}-#{Date.today.iso8601}"
        mid      = find_auto_memory(memory_type, mem_name, uid)

        unless mid
          mem_data = @client.create_memory(memory_type: memory_type, name: mem_name, user_id: uid)
          mid = mem_data["memory_id"] || mem_data["id"]
        end

        @client.add_data_to_memory(mid, [data_id]) if mid && data_id
        result["memory_id"] = mid
      end

      result
    end

    def search(query, limit: 10, memory_type: nil, memory_ids: nil, use_ai: false, user_id: nil)
      uid = user_id || @user_id

      if use_ai
        data = @client.ai_query(query, memory_ids: memory_ids)
        return data.is_a?(Hash) ? [data] : data
      end

      if memory_type
        data  = @client.list_memories(memory_type: memory_type, limit: limit, user_id: uid)
        items = data.is_a?(Array) ? data : (data["items"] || [])
        return items.first(limit)
      end

      data  = @client.list_user_data(user: uid, limit: limit)
      items = data.is_a?(Array) ? data : (data["items"] || [])
      items
    end

    def get(data_id, version: nil)
      content = @client.get_data(data_id, version: version)
      meta = begin; @client.get_metadata(data_id); rescue; {}; end
      result = { "data_id" => data_id }
      result.merge!(meta) if meta.is_a?(Hash)
      result["content"] = content
      result
    end

    def delete(data_id)
      @client.delete_data(data_id)
    end

    def entities(query, entity_type: nil, limit: 20, user_id: nil)
      data = @client.search_entities(query, user_id: user_id || @user_id, entity_type: entity_type, limit: limit)
      data.is_a?(Array) ? data : []
    end

    def related(data_id, user_id: nil)
      data = @client.get_data_entities(data_id, user_id: user_id || @user_id)
      data.is_a?(Array) ? data : []
    end

    def compress(memory_id, archive_originals: false, max_summary_length: 2000, user_id: nil)
      @client.compress_memory(memory_id, archive_originals: archive_originals,
                               max_summary_length: max_summary_length,
                               user_id: user_id || @user_id)
    end

    private

    def find_auto_memory(memory_type, name, user_id)
      data  = @client.list_memories(memory_type: memory_type, limit: 50, user_id: user_id)
      items = data.is_a?(Array) ? data : (data["items"] || [])
      match = items.find { |mem| mem["name"] == name }
      match && (match["memory_id"] || match["id"])
    rescue StandardError
      nil
    end
  end
end
