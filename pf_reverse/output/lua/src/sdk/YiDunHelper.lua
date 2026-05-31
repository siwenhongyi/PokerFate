local P = {
    token = "",
    sdkVersion = "1.4.10",
    sdkVersion2 = "1.5.3", --todo

    getedToken = false,
    reportData = {},
}
YiDunHelper = P

function P:init()


    if bee.checkVersion(self.sdkVersion2) then

    elseif bee.checkVersion(self.sdkVersion) then
        if not bee.isEditor then
            CS.DeviceFingerprint.Init()
        end
    end
end

function P:setToken(token)
    self.token = token
    self.getedToken = true
end

function P:setRoleInfo()
    if not bee.checkVersion(self.sdkVersion) then
        return
    end

    local account = PlayerModel:getTestDeviceID() or ""
    local uid = PlayerModel:getUid()
    local name = PlayerModel:getName()
    local lv = PlayerModel:getCurLevel()
    CS.DeviceFingerprint.SetRoleInfo(account, uid, name, G_HTTP_URL, G_PACKAGE_TYPE, lv)
end

--获取token
-- function P:getToken()
--     if bee.checkVersion(self.sdkVersion) then
--         CS.DeviceFingerprint.GetToken()
--     end
-- end

--上报数据
function P:setReportData(channel, type, account)
    self.reportData = {}
    -- self.reportData.token = self.token
    self.reportData.account = account or "unknown"
    self.reportData.ip = "unknown"
    self.reportData.os = bee.pfsys
    self.reportData.sceneData = {
        registerOrLogType = tostring(channel) or "iphone",
        operationType = type or "register",
        appChannel = "1",
    }

    if bee.checkVersion(self.sdkVersion) then
        if bee.checkVersion(self.sdkVersion2) then
            CS.DeviceFingerprint.Instance:GetToken()
        else
            if not bee.isEditor then
                CS.DeviceFingerprint.GetToken()
            else
                self.reportData.token = ''
                bee.emit("evt_yidunTokenCallback")
            end
        end

        local tag
        tag = bee.schedule(0.02, function ()
            if self.getedToken then
                self.getedToken = false
                self.reportData.token = self.token
                bee.emit("evt_yidunTokenCallback")
                scheduler:removeTag(tag)
            end
        end)
    else
        self.reportData.token = ''
        bee.emit("evt_yidunTokenCallback")
    end
end
function P:getReportData()
    return self.reportData
end

return P