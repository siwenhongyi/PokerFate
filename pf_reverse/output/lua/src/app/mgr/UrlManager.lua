local P = {
    _httpIndex = 1,
    _serverIndex = 1,
}
UrlManager = P

function P:init()
    self._httpIndex = LocalStore:getIntegerForKey("http_index", 1)
    self._serverIndex = LocalStore:getIntegerForKey("server_index", 1)
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
    for _, v in ipairs(servers) do
        table.insert(self._htts, v.http_host)
        table.insert(self._websockets, v.server_host)
    end
end

-- "server":{"http":[{"host":"dev-login.poker-fate.com","port":0}],"websocket":[{"host":"dev-entry.poker-fate.com","port":9012}]}
function P:setServerUrls(https, websockets)
    self._htts = https
    local h = "https://"
    if not string.find(G_HTTP_URL, "https") then
        h = "http://"
    end
    for _, v in ipairs(https) do
        if string.find(v.host, "http") then
            if v.port > 0 then
                v.http = v.host .. ":" .. v.port .. "/"
            else
                v.http = v.host .. "/"
            end
        else
            if v.port > 0 then
                v.http = h .. v.host .. ":" .. v.port .. "/"
            else
                v.http = h .. v.host .. "/"
            end
        end
    end
    self._websockets = websockets
    for _, v in ipairs(websockets) do
        if string.find(v.host, "ws://") or string.find(v.host, "wss://") then
            if v.port > 0 then
                v.ws = v.host .. ":" .. v.port .. "/"
            else
                v.ws = v.host .. "/"
            end
        else
            if v.port > 0 then
                v.ws = "ws://" .. v.host .. ":" .. v.port .. "/"
            else
                v.ws = "ws://" .. v.host .. "/"
            end
        end
    end
end

