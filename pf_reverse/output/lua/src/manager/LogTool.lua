-- 埋点上报管理器
local P={
    TAG = "LOG_EVENTS",
    project = "bh-jp",
    serviceAddr = "ap-northeast-1.log.aliyuncs.com",
    logstore = "client-dev",

    os = bee.isAndroid and 1 or (bee.isIos and 2 or 3),
    env = "2",
    _evts = {},
    _isSending = false,
    _cacheNum = 200,

    ab = 1,   -- AB 测试标志
}

if bee.isDev then   -- 测试服
elseif bee.isDmod then  -- 时间测试服
    P.env = "2"
    P.logstore = "client-time"
elseif bee.isPre then   -- 预发布服
    P.env = "2"
    P.logstore = "client-pre"
elseif bee.isRelease then   -- 正式服
    P.env = "1"
    P.logstore = "client-prod"
end

LogTool = P


local host = "https://" .. P.project .. "." .. P.serviceAddr .. "/logstores/" .. P.logstore .. "/track?APIVersion=0.6.0&"

function P:init(cacheNum)
    self._evts = LocalStore:getTableData(self.TAG) or {}
    self._cacheNum = cacheNum or 200
    self.ab = SdkHelper:isTestB() and 2 or 1

    local _publicParams = {
        "os=" .. P.os,
        "phone=" .. CS.SdkHelper.getModel(),
        -- "system=" .. CS.SdkHelper.getBrand(),
        -- "system=" .. (bee.isAndroid and "android" or (bee.isIos and "ios" or "windows")),
        "system=" .. CU.SystemInfo.operatingSystem,
        "did=" .. SdkHelper:getDeviceID(),
        "env=" .. P.env,
        "ver=" .. G_UPDATE_VERSION,
        "chnl=" .. G_CHNL_ID,
        "vers=" .. G_APP_VERSION,
    }

    host = host .. table.concat(_publicParams, "&")
end

function P:setAb(ab)
    self.ab = ab
end

-- 设置停止收集上报
function P:setPause(flag)
    self._isPaused = flag
end

-- 上报埋点
function P:logEvent(key, ...)
    if self._isPaused or P.logstore == "" then
        return
    end
    local args, t, vi, fi = {...}, nil, 1, 1
    local sd = {
        "key=" .. key,
    }
    for _, v in pairs(args) do
        t = type(v)
        if "table" == t then
            for kk, vv in pairs(v) do
                sd[#sd + 1] = kk .. "=" .. vv
                if string.sub(kk, 1, 1) == "f" then
                    fi = fi + 1
                else
                    vi = vi + 1
                end
            end
        elseif "string" == t then
            sd[#sd + 1] = "v" .. vi .. "=" .. v
            vi = vi + 1
        else
            sd[#sd + 1] = "f" .. fi .. "=" .. v
            fi = fi + 1
        end
    end
    self:sendEvent(sd, key)
end

-- 上报埋点，params: table 格式，可选参数，会把里面的所有k-v都上报
function P:addLog(name, params, ...)
    if self._isPaused then
        return
    end
    self:logEvent(name, params, ...)
end

function P:sendEvent(e, key)
    local url = "&" .. table.concat(e, "&") .. "&" .. table.concat(self:getBaseParams(), "&")
    if not bee.isRelease and key ~= "net_delay" and key ~= "http_delay" then
        CS.NLog.Log(CS.UnityEngine.Color.cyan, " [log event] ".. url)
    end
    self:sendUrl(url)
end

function P:getBaseParams()
    return {
        "ts=" .. os.time(),
        "reg=" .. (PlayerModel and PlayerModel:getRegisterTime() or ""),
        "uid=" .. (PlayerModel and PlayerModel:getUid() or ""),
    }
end

function P:sendUrl(url)
    if #self._evts > self._cacheNum then
        table.remove(self._evts, 1)
    end
    self._evts[#self._evts+1] = url
    if not self._isSending then
        LocalStore:saveTableData(self.TAG, self._evts)
        self:_sendEvent()
    else
        LocalStore:saveTableData(self.TAG, self._evts)
    end
end

function P:_sendEvent()
    if not self._isSending and #self._evts > 0 then
        self._isSending = true
        local evt = self._evts[1]
        CS.HttpManager.Instance:get(host .. evt, function(text)
            -- print("[log event] sendEvent suc", host .. evt)
            self._isSending = false
            if evt == self._evts[1] then
                table.remove(self._evts, 1)
            end
            if LocalStore then
                LocalStore:saveTableData(self.TAG, self._evts)
                self:_sendEvent()
            end
        end, function()
            -- print("[log event] sendEvent fail!", host .. evt)
            self._isSending = false
            if not self._isOncing then
                self._isOncing = true
                scheduler:once(10, function()
                    self._isOncing = false
                    self:_sendEvent()
                end)
            end
        end, 10, "")
    end
end


function bee.logEvent(name, ...)
    LogTool:logEvent(name, ...)
end

function bee.log(name, ...)
    LogTool:logEvent(name, ...)
end

return P