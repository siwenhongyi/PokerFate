local P = {
    token = "",
    sdkVersion = "1.4.10",
}
YiDunHelper = P

function P:init()
    if not bee.checkVersion(self.sdkVersion) then
        return
    end
    
    CS.DeviceFingerprint.Init()
    self:getToken()
end

function P:setToken(token)
    self.token = token
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
function P:getToken()
    if bee.checkVersion(self.sdkVersion) then
        CS.DeviceFingerprint.GetToken()
    end
end

--上报数据
function P:getReportData(channel, type, account)
    local args = {}
    args.token = self.token
    args.account = account or "unknown"
    args.ip = "unknown"
    args.os = bee.pfsys
    args.sceneData = {
        registerOrLogType = tostring(channel) or "iphone",
        operationType = type or "register",
        appChannel = "1",
    }
    self:getToken()
    return args
end

return P