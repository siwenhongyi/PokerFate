local P = {
    _httpIndex = 1,
    _serverIndex = 1,
    _selectKey = nil,   -- 选择的线路key
}
UrlManager = P

function P:init()
    self._httpIndex = LocalStore:getIntegerForKey("http_index", 1)
    self._serverIndex = LocalStore:getIntegerForKey("server_index", 1)
    self._selectKey = LocalStore:getStringForKey("net_select_key", nil)
end

function P:setSelectKey(key)
    self._selectKey = key
    if not key then
        LocalStore:deleteValueForKey("net_select_key")
    else
        LocalStore:setStringForKey("net_select_key", key)
    end
end

function P:getSelectKey()
    return self._selectKey
end

function P:nextHttpUrl()
    local old = UrlManager:getHttpUrl()
    self._httpIndex = self._httpIndex + 1
    if self._htts and #self._htts > 0 and self._httpIndex > #self._htts then
        self._httpIndex = 1
    end
    LocalStore:setIntegerForKey("http_index", self._httpIndex)
	bee.logEvent("http_change", UrlManager:getHttpUrl(), old)
end

function P:getHttpUrl()
    if self._htts and #self._htts > 0 then
        if self._selectKey then
            for _, v in ipairs(self._urls) do
                if v.http_host == self._selectKey then
                    return v.http_host
                end
            end
        end
        if self._httpIndex > #self._htts then
            self._httpIndex = 1
        end
        return self._htts[self._httpIndex]
    end
    if _G["G_HTTP_URL_" .. self._httpIndex] then
        return _G["G_HTTP_URL_" .. self._httpIndex]
    end
    if self._httpIndex ~= 1 then
        self._httpIndex = 1
        LocalStore:setIntegerForKey("http_index", self._httpIndex)
    end
    return G_HTTP_URL
end

function P:nextServerUrl()
    local old = UrlManager:getServerUrl()
    self._serverIndex = self._serverIndex + 1
    if self._websockets and #self._websockets > 0 and self._serverIndex > #self._websockets then
        self._serverIndex = 1
    end
    LocalStore:setIntegerForKey("server_index", self._serverIndex)
	bee.logEvent("net_change", UrlManager:getServerUrl(), old)
end

function P:getServerUrl()
    if G_SERVER_URL then
        return G_SERVER_URL
    end
    if self._websockets and #self._websockets > 0 then
        if self._selectKey then
            for _, v in ipairs(self._urls) do
                if v.http_host == self._selectKey then
                    return v.server_host
                end
            end
        end

        if self._serverIndex > #self._websockets then
            self._serverIndex = 1
        end
        return self._websockets[self._serverIndex]
    end
    return G_SERVER_URL
end

function P:setHosts(servers)
    self._htts = {}
    self._websockets = {}
    self._urls = servers
    for _, v in ipairs(servers) do
        table.insert(self._htts, v.http_host)
        table.insert(self._websockets, v.server_host)
    end
end

function P:getHosts()
    if self._urls then
        return self._urls
    end
    local ret = {
        {http_host = G_HTTP_URL},
    }
    if G_HTTP_URL_2 then
        table.insert(ret, {http_host = G_HTTP_URL_2})
    end
    if G_HTTP_URL_3 then
        table.insert(ret, {http_host = G_HTTP_URL_3})
    end
    if G_HTTP_URL_4 then
        table.insert(ret, {http_host = G_HTTP_URL_4})
    end
    return ret
end

return P