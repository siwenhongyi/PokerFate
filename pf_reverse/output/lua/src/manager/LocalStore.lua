local P = {
	_datas = {}
}
LocalStore = P

-- 本地存储管理器
function P:clear()
	self._datas = {}
end

-- 检查每日标志是否可用
-- noAutoSet: 检查可用后不设置为不可用
-- offsetDay: 检查多少天内的
function P:isDailyTagValid(tag, noAutoSet, offsetDay)
	local tagValue = self:getStringForKey(tag)
	local dateStr = os.date("%Y%m%d")
	if tagValue == dateStr then
		return false
	end
	if offsetDay and tagValue and tagValue ~= "" then
		if tonumber(tagValue) + offsetDay >= tonumber(dateStr) then
			return false
		end
	end
	if noAutoSet then
		return true
	end
	self:setStringForKey(tag, dateStr)
	return true
end

-- 检查每日标志是否可用，使用目标时区跨天时间点
function P:isDailyTagValidCrossDay(tag, noAutoSet, offsetDay)
	local tagValue = self:getStringForKey(tag)
	local zone = TimeHelp:getTimeZone()
	local dt = bee.getServerTime() + (TimeHelp.targetZone - zone - TimeHelp.crossHour) * 3600
	local dateStr = os.date("%Y%m%d", dt)
	if tagValue == dateStr then
		return false
	end
	if offsetDay and tagValue and tagValue ~= "" then
		if tonumber(tagValue) + offsetDay >= tonumber(dateStr) then
			return false
		end
	end
	if noAutoSet then
		return true
	end
	self:setStringForKey(tag, dateStr)
	return true
end

-- 检查每周标志是否可用
function P:isWeekTagValid(tag, week)
	if not week then week = os.date("%W", os.time()) end
	local tagValue = self:getStringForKey(tag)
	if tagValue == week then
		return false
	end
	self:setStringForKey(tag, week)
	return true
end

-- 检查标志是否可用
-- noAutoSet: 检查可用后不设置为不可用
function P:isTagValid(tag, noAutoSet)
	if self:getBoolForKey(tag, false) then
		return false
	end
	if noAutoSet then
		return true
	end
	self:setBoolForKey(tag, true)
	return true
end

function P:getTableData(tag)
	if self._datas[tag] then
		return self._datas[tag]
	end
	local dataTb = nil
	if not tag or tag == "" then
		return dataTb
	end
	if G_RUN_IN_JOB then return dataTb end
	
	local cacheStr = CU.PlayerPrefs.GetString(tag, "")
	if cacheStr and cacheStr ~= "" then
		dataTb = json.decode(cacheStr)
		self._datas[tag] = dataTb
	end
	return dataTb
end

-- 保存数据表
function P:saveTableData(tag, dataTb)
	if G_RUN_IN_JOB then return end
	if tag and dataTb then
		self._datas[tag] = dataTb
		local dataStr = json.encode(dataTb)
		CU.PlayerPrefs.SetString(tag, dataStr or "")
	end
end

function P:getStringForKey(key, default)
	if G_RUN_IN_JOB then return default end
	local ret = CU.PlayerPrefs.GetString(key, "")
	if nil ~= default and "" == ret then
		ret = default
	end
	return ret
end

function P:setStringForKey(key, val)
	if G_RUN_IN_JOB then return end
	CU.PlayerPrefs.SetString(key, val)
end

function P:DeleteAll(key, val)
	local app_full_version = self:getStringForKey("app_full_version")
	local load_slient_result = self:getStringForKey("load_slient_result")
	CU.PlayerPrefs.DeleteAll()
	if app_full_version and "" ~= app_full_version then
		self:setStringForKey("app_full_version", app_full_version)
	end
	if load_slient_result and "" ~= load_slient_result then
		self:setStringForKey("load_slient_result", load_slient_result)
	end
	CU.PlayerPrefs.Save()
	self._datas = {}
end


function P:getBoolForKey(key, default)
	if G_RUN_IN_JOB then return default end
	local ret = CU.PlayerPrefs.GetInt(key, -1)
	if nil ~= default and -1 == ret then
		ret = default
	elseif 1 == ret then
		ret = true
	else
		ret = false
	end
	return ret
end

function P:setBoolForKey(key, val)
	if G_RUN_IN_JOB then return end
	CU.PlayerPrefs.SetInt(key, val and 1 or 0)
end

function P:getIntegerForKey(key, default)
	if G_RUN_IN_JOB then return default end
	local ret = CU.PlayerPrefs.GetInt(key, 0)
	if default and 0 == ret then
		ret = default
	end
	return ret
end

function P:setIntegerForKey(key, val)
	if G_RUN_IN_JOB then return end
	CU.PlayerPrefs.SetInt(key, val)
end

function P:deleteValueForKey(key)
	CU.PlayerPrefs.DeleteKey(key)
	self._datas[key] = nil
end

