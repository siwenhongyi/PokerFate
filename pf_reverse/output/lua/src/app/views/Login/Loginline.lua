local P = class("Loginline", UiDialog)

function P:onAwake()
    local Panel = self:find("AnimRoot/Center/Panel")
    
    bee.addClick(self:find("CloseButton", Panel), function()
        self:hideUI()
    end)
    
    self.ButtonLines = {
        self:find("Views/ButtonLine01", Panel),
        self:find("Views/ButtonLine02", Panel),
        self:find("Views/ButtonLine03", Panel),
        self:find("Views/ButtonLine04", Panel),
    }

    for k, v in ipairs(self.ButtonLines) do
        bee.setText(self:find("BgText/TextLine", v), _F("LAB_LOGIN_ROUTE_02", k))
        self:find("loginline_garment_tab", v):SetActive(false)
        self:find("loginline_icon_01", v):SetActive(false)
        bee.addClick(v, function()
            if not bee.checkCd("Loginline_changeLine", 1) then
                return
            end
            Game:playSound("ui_button_confirm")
            bee.logEvent("login-selectroute-access", k)

            if self._urls and self._urls[k] and self._urls[k].http_host ~= UrlManager:getSelectKey() then
                if self._urls[k].http_host ~= self._defaultUrl then
                    UiManager:showTip({
                        text = _T("LAB_LOGIN_ROUTE_07"),
                        button = 2,
                        onSure = function()
                            bee.logEvent("login-selectroute-confirm", k)
                            self:onChangeNet(self._urls[k])
                        end,
                        onCancel = function(isClose)
                            if isClose then
                                bee.logEvent("login-selectroute-close", k)
                            else
                                bee.logEvent("login-selectroute-cancel", k)
                            end
                        end
                    })
                else
                    self:onChangeNet(self._urls[k])
                end
            end
        end)
    end
end

function P:onShow()
    self.transform.localPosition = bee.v3zero
    self._defaultUrl = nil
    self._urls = UrlManager:getHosts()
    for _, v in ipairs(self._urls) do
        v.delay = nil
    end
    
    self:refreshUI()

    self:tryPing()
end

function P:onChangeNet(url)
    UrlManager:setSelectKey(url.http_host)
    self:refreshUI()
    if Net:isConnected() then
        Net:closeSocket()
        -- LoginModel:reConnectWithCheck()
        self:once(-1, function()
            self:doReconnect(url)
        end)
    elseif PlayerModel:isLogin() then
        self:doReconnect(url)
    else
        self:refreshUI()
    end
end

function P:doReconnect(url)
    LoginModel:checkReConnect()
    -- LoginModel:reConnect(function(ret)
    --     if ret then
    --         self:refreshUI()
    --     else
    --         UrlManager:setSelectKey(nil)
    --         self:once(-1, function()
    --             if url and UrlManager:getServerUrl() == url.server_host then
    --                 UrlManager:nextServerUrl()
    --             end
    --             LoginModel:reConnect()
    --         end)
    --     end
    -- end)
end

function P:tryPing()
    local dt = scheduler.timeSpend
    local num = #self._urls
    for _, v in ipairs(self._urls) do
        Net:getUrl(v.http_host .. "ping", function()
            v.delay = scheduler.timeSpend - dt
            num = num - 1
            if num <= 0 then
                self:refreshDefalut()
                self:refreshUI()
            end
        end, 
        function()
            v.delay = 999
            num = num - 1
            if num <= 0 then
                self:refreshDefalut()
                self:refreshUI()
            end
        end, true, true)
    end
end

function P:refreshDefalut()
    self._defaultUrl = self._urls[1].http_host
    local delay = self._urls[1].delay
    for _, v in ipairs(self._urls) do
        if v.delay and v.delay < delay then
            self._defaultUrl = v.http_host
            delay = v.delay
        end
    end
end

function P:refreshUI()
    local key = UrlManager:getSelectKey()
    local curUrl = UrlManager:getHttpUrl()
    for k, v in ipairs(self.ButtonLines) do
        local url = self._urls[k]
        if url then
            v:SetActive(true)
            if not key then
                self:find("BgText/TextSel", v):SetActive(url.http_host == curUrl)
            else
                self:find("BgText/TextSel", v):SetActive(url.http_host == key)
            end
            self:find("loginline_garment_tab", v):SetActive(url.http_host == self._defaultUrl and url.delay and url.delay ~= 999)
            self:find("loginline_icon_01", v):SetActive(true)
            if url.delay then
                if url.delay == 999 then
                    self:find("TextDelay01", v):SetActive(false)
                    self:find("TextDelay02", v):SetActive(false)
                    self:find("TextDelay03", v):SetActive(false)
                    bee.setIcon(self:find("loginline_icon_01", v), "Loginline[loginline_icon_03]")
                elseif url.delay < 0.2 then
                    self:find("TextDelay01", v):SetActive(true)
                    self:find("TextDelay02", v):SetActive(false)
                    self:find("TextDelay03", v):SetActive(false)
                    bee.setText(self:find("TextDelay01", v), _F("LAB_LOGIN_ROUTE_04", math.floor(url.delay * 1000)))
                    bee.setIcon(self:find("loginline_icon_01", v), "Loginline[loginline_icon_01]")
                elseif url.delay <= 0.5 then
                    self:find("TextDelay01", v):SetActive(false)
                    self:find("TextDelay02", v):SetActive(true)
                    self:find("TextDelay03", v):SetActive(false)
                    bee.setText(self:find("TextDelay02", v), _F("LAB_LOGIN_ROUTE_04", math.floor(url.delay * 1000)))
                    bee.setIcon(self:find("loginline_icon_01", v), "Loginline[loginline_icon_02]")
                else
                    self:find("TextDelay01", v):SetActive(false)
                    self:find("TextDelay02", v):SetActive(false)
                    self:find("TextDelay03", v):SetActive(true)
                    bee.setText(self:find("TextDelay03", v), _F("LAB_LOGIN_ROUTE_04", math.floor(url.delay * 1000)))
                    bee.setIcon(self:find("loginline_icon_01", v), "Loginline[loginline_icon_03]")
                end
            end
        else
            v:SetActive(false)
        end
    end
end

function P:evt_hideUiWhenAction(isVisible)
    self:onUiBlur(not isVisible, "evt_hideUiWhenAction", true)
end

return P