-- 手机震动管理器
local P = {
    -- 震动强度级别定义
    _amplitudes = {150, 200, 255},

    -- 震动时长
    _vtimes = {10, 15, 15},

    -- 震动间隔时长
    _intervals = {50, 75, 100},

    -- 是否支持震动
    _enable = true,

    _isOn = true,
}
VibrateManager = P

if bee.isAndroid then
    local timeScale = nil
    local sys = CS.SdkHelper.getBrand()
    local model = CS.SdkHelper.getModel()
    print("[VibrateManager] Operate Brand ==== ggg", sys, model)
    if sys == "samsung" then
        timeScale = 3
        if string.find(model, "G980F") then
            timeScale = 1
        elseif string.find(model, "G98") then
            P._enable = false
        elseif string.find(model, "A50") then
        elseif string.find(model, "G88") then
            timeScale = 4.5
        elseif string.find(model, "G973U") then
            timeScale = 0.8
        elseif string.find(model, "SM-N975U") then
            timeScale = 1
        end
    elseif sys == "Redmi" then
        timeScale = 2
    elseif sys == "vivo" then
        timeScale = 3
        if string.find(model, "V2049") then
            timeScale = 2
        end
    elseif sys == "HUAWEI" then
        timeScale = 2
    elseif sys == "google" then
        timeScale = 0.67
        P._amplitudes = {75, 125, 180}
    end
    if timeScale then
        for k, v in ipairs(P._vtimes) do
            P._vtimes[k] = math.floor(v * timeScale)
        end
    end
elseif bee.isIos then
    _intervals = {100, 125, 150}
end

-- 是否能够响应震动
function P:isCanVibrate()
    return self._enable
end

-- 震动一次，level: 震动级别
function P:vibrateOnce(level)
    if not self._enable or not P._isOn then
        return
    end
    if bee.isIos then
        CS.SdkHelper.vibrate2(tostring(self._vtimes[level]) .. ",0", tostring(self._amplitudes[level]) .. ",0")
    else
        CS.SdkHelper.vibrate2(tostring(self._vtimes[level]), tostring(self._amplitudes[level]))
    end
end

-- 震动多次， params = {强度level，间隔level, ...}
function P:vibrate(params)
    if not self._enable or not P._isOn or not params then
        return
    end
    if #params == 1 then
        self:vibrateOnce(params[1])
        return
    end
    local dts, amplitudes = {}, {}
    for i = 1, #params, 2 do
        amplitudes[#amplitudes + 1] = self._amplitudes[params[i]]
        dts[#dts + 1] = self._vtimes[params[i]]

        if i <= #params - 1 then
            amplitudes[#amplitudes + 1] = 0
            if self._intervals[params[i + 1]] then
                dts[#dts + 1] = self._intervals[params[i + 1]]
            else
                dts[#dts + 1] = params[i + 1]
            end
        end
    end
    CS.SdkHelper.vibrate2(table.concat(dts, ","), table.concat(amplitudes, ","))
end

-- 是否开启震动
function P:isOn()
    return LocalStore:getBoolForKey("open_vibrate", true)
end

function P:setIsOn(flag)
    LocalStore:setBoolForKey("open_vibrate", flag)
    P._isOn = flag
end

function P:init()
    if P._enable and tpl_vibrate then
        -- P._isOn = P:isOn()
        bee.vibrate = function(params)
            if not params or not SettingModel or (params.kind and not SettingModel:isCanVibrate(params.kind)) then
                return
            end
            if self._vibrate_dt == scheduler.timeSpend then
                return
            end
            self._vibrate_dt = scheduler.timeSpend
            if params.id then
                if bee.isEditor then
                    print("[VibrateManager] vibrate <color=#FC4420>" .. params.id .. "</color>")
                end
                P:vibrate(params.vibrates)
            else
                P:vibrate(params)
            end
        end
        if not P._clickFunc then
            P._clickFunc = bee.addClick
        end
        bee.addClick = function(obj, callback, isRemove)
            P._clickFunc(obj, function(...)
                bee.vibrate(tpl_vibrate.button)
                callback(...)
            end, isRemove)
        end
        if not P._checkFunc then
            P._checkFunc = bee.onCheck
        end
        bee.onCheck = function(obj, callback)
            P._checkFunc(obj, function(isOn, ...)
                bee.vibrate(tpl_vibrate.button)
                callback(isOn, ...)
            end)
        end
    else
        bee.vibrate = function(params)
        end
    end
end

return P