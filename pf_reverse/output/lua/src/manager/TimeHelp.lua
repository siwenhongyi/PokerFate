local P = {
    _localZone = nil,   -- 本地时区

    targetZone = 9,     -- 目标时区，东9区东京时间
    crossHour = 4,      -- 跨天时间点
    crossHourUTC = 4 - 9 + 24
}
TimeHelp = P

function P:getTimeStr(et)
    return string.format("%02d:%02d:%02d", math.floor(et / 3600), math.floor((et % 3600) / 60), math.floor(et % 60))
end

function P:getTimeStrHMS(et)
    if et >= 3600 then
        return string.format("%02d:%02d:%02d", math.floor(et / 3600), math.floor((et % 3600) / 60), math.floor(et % 60))
    end
    return string.format("%02d:%02d", math.floor(et / 60), math.floor(et % 60))
end

function P:getDateTimeStr(dt, sepY, sepH)
    sepY = sepY or "-"
    sepH = sepH or ":"
    return os.date("%Y"..sepY.."%m"..sepY.."%d %H"..sepH.."%M"..sepH.."%S", dt)
end

function P:getDateTimeStrM(dt, sepY, sepH)
    sepY = sepY or "-"
    sepH = sepH or ":"
    return os.date("%Y"..sepY.."%m"..sepY.."%d %H"..sepH.."%M", dt)
end

function P:getDateStr(dt, sep)
    sep = sep or "-"
    return os.date("%Y"..sep.."%m"..sep.."%d", dt)
end

function P:getTimeLeftStr(dt, needSecond)
    if dt < 0 then
        dt = 0
    end
    local s = ""
    local isDay, isHour = false, false
	if dt > 86400 then
		local d = math.floor(dt / 86400)
		s = s .. _F("LAB_TIME_DAY", d)
        dt = dt % 86400
        isDay = true
    end
	if dt > 3600 then
        if LAN:getLanguage() == "en" and s ~= "" then
            s = s .. " "
        end
        if isDay then
            local h = math.ceil(dt / 3600)
            s = s .. _F("LAB_TIME_HOURS", h)
        else
            local h = math.floor(dt / 3600)
            s = s .. _F("LAB_TIME_HOURS", h)
        end
        dt = dt % 3600
        isHour = true
    end
    if not isDay then
        if dt >= 60 then
            if LAN:getLanguage() == "en" and s ~= "" then
                s = s .. " "
            end
            if needSecond then
                local m = math.floor(dt / 60)
                s = s .. _F("LAB_TIME_MINUTES", m)
            else
                local m = math.ceil(dt / 60)
                s = s .. _F("LAB_TIME_MINUTES", m)
            end
            dt = dt % 60
        end
        if not isHour and dt > 0 and needSecond then
            if LAN:getLanguage() == "en" and s ~= "" then
                s = s .. " "
            end
            s = s .. _F("LAB_TIME_SECONDS", dt)
        end
    end
    return s
end

-- 获取本机时区的当天剩余秒数，timeStr: 07:59:59
function P:getDayLeftDt(timeStr)
    local parts = string.split(timeStr, ":")
    local hour = tonumber(parts[1]) or 0
    local min = tonumber(parts[2]) or 0
    local sec = tonumber(parts[3]) or 0
    local now = os.time()
    local t = os.date("*t", now)
    local targetTime = os.time({year = t.year, month = t.month, day = t.day, hour = hour, min = min, sec = sec})
    return targetTime - now + (self.targetZone - self:getTimeZone()) * 3600
end

-- 获取本机时区
function P:getTimeZone()
    if not self._localZone then
        local now = os.time()
        local zone = os.difftime(now, os.time(os.date("!*t", now))) / 3600
        local isdst = os.date("*t", now).isdst
        if isdst then zone = zone + 1 end
        self._localZone = zone
    end
    return self._localZone
end

-- 获取在目标时区的时间
function P:getTimeInZone(dt, zone)
    local now = (dt or os.time()) + ((zone or self.targetZone) - self:getTimeZone()) * 3600
    local t = os.date("*t", now)
    return t
end

--转回本地时区  dt 目标时区时间戳
function P:getTimeInLocalZone(dt, zone)
    return (dt or os.time()) - ((zone or self.targetZone) - self:getTimeZone()) * 3600
end

-- 获取时间结构 t 在目标时区的时间戳
function P:getSecondInZone(t, zone)
    local now = os.time(t)
    now = now - ((zone or self.targetZone) - self:getTimeZone()) * 3600
    return now
end

-- 获取农历月/日
function P:getLunarMonthAndDay(time)
    if not time then
        time = bee.getServerTime()
    end
    local m = CS.Utils.GetLunarMonth(time)
    local d = CS.Utils.GetLunarDay(time)

    return m, d
end

-- 判断时间戳 dt 是否在今天的跨天周期内
-- 游戏日 = targetZone 时区每天的 crossHour(4点) 刷新，即 UTC 19:00 换日
-- 先算出当前游戏日起始的跨天时间戳，再判断 dt 是否落在该日起的 24 小时内
function P:isInToday(dt)
    if not dt then
        dt = bee.getServerTime()
    end
    local now = bee.getServerTime()
    -- 跨天点在本地时区的时刻（目标时区每天 crossHour 点，如东9区4点 → 本地(4-(9-本地时区))点）
    local crossHourLocal = (self.crossHour - (self.targetZone - self:getTimeZone())) % 24
    local t = os.date("*t", now)
    -- 今天本地时间的跨天点时间戳
    local crossToday = os.time({year = t.year, month = t.month, day = t.day, hour = crossHourLocal, min = 0, sec = 0})
    -- 还没到今天的跨天点，说明当前游戏日从昨天的跨天点开始
    local crossTime = crossToday
    if now < crossToday then
        crossTime = crossToday - 86400
    end
    -- 传入时间落在 [跨天点, 跨天点+24小时) 内，即为同一个游戏日
    return dt >= crossTime and dt < crossTime + 86400
end

return P