-- 本地推送管理

local P = {
	_isInited = false
}
MobileNotificationsManager = P

-- 本地记录是否推送key
local IS_NOTIFICATIONS_KEY = "is_show_notifications"
-- 推送通知标题(游戏名)key
local NOTIFICATION_TITLE_KEY = "LAB_GAME_NAME"
-- 允许推送时间字段名
local PUSH_ALLOW_TIME_KEY = "PushAllowTime"
-- 每日推送次数刷新时间
local PUSH_REFRESH_TIME = "00:00:00"

-- 推送类型
local NOTIFICATION_TYPE =
{
	LIFE_FULL = 1,			-- 体力满
	LIFE_ADD = 2,			-- 体力+1
	ASSIGN_TIME = 3,		-- 规定时间
}

local NOTIFICATION_TYPE_STORE_NAME_STR = "notifications_type_"
local NOT_USE_FIREBASE = string.find(SdkHelper:getDeviceModel(), "HUAWEI") 
-- NOT_USE_FIREBASE = true
function P:init()
	if self._isInited then
		return
	end
	self._isInited = true
	print("==== gggggggg MobileNotificationsManager init ====", NOT_USE_FIREBASE)
	if NOT_USE_FIREBASE then return end
	bee.on("evt_onApplicationPause", function(paused)
		if paused then
			if bee.checkCd("CalculatePushNotifications", 2) then
				-- 计算可能需要的通知
				self:CalculatePushNotifications()
				self.isLog = false
			end
		else
			if bee.checkCd("CheckNotificationIntentData", 2) then
				-- 清除所有已安排通知
				CS.MobileNotificationsMgr.Instance:CancelAllNotifications()
				self:CheckNotificationIntentData()
			end
		end
	end)

	bee.on("evt_GetFirebaseToken", self["evt_GetFirebaseToken"], self)

	-- 检查是否使用谷歌服务
	CS.MobileNotificationsMgr.Instance:CheckGooglePlay()
	-- 检查是否有推送附带消息
	self:CheckNotificationIntentData()
end

function P:evt_GetFirebaseToken()
	if NOT_USE_FIREBASE then return end
end

-- 计算恢复下一点体力时间
function P:CalHpNextRecoverTime()
	local curHp = PlayerModel:getHp()

	-- 体力值已满，或下一点体力为满值，不需要计算下一点体力值
	if curHp >= PlayerModel:getMaxHp() then
		return 0
	end

	-- 下一点体力值恢复时间
	local nextHpRecoverTime = PlayerModel:getNextHpRecoverTime()
	local infiniteTimeFinishTime = ItemModel:getTimeLimitPropLeftTime(GPropType.Hp)

	-- 无限体力期间不进行推送，无限体力结束后如果有体力增加/满值立刻推送
	return math.max(nextHpRecoverTime, infiniteTimeFinishTime)
end

-- 计算体力全部恢复时间
function P:CalHpFullTime()
	local curHp = PlayerModel:getHp()

	-- 需要恢复的体力值
	local waitRecoverHp = PlayerModel:getMaxHp() - curHp

	-- 体力值已满，不需要计算体力值
	if waitRecoverHp <= 0 then
		return 0
	end

	local needTime = PlayerModel:getNextHpRecoverTime() + (waitRecoverHp - 1) * Config.HP_RECOVER_SECOND
	local infiniteTimeFinishTime = ItemModel:getTimeLimitPropLeftTime(GPropType.Hp)

	-- 无限体力期间不进行推送，无限体力结束后如果有体力增加/满值立刻推送
	return math.max(needTime, infiniteTimeFinishTime)
end

-- 计算指定时间
function P:CalAssignPushTime(timeStr)
	
	-- 第二天的指定时间触发
	return TimeLib.string2time(self:GetTimeStr(timeStr)) + 86400
end

-- 判断是否在可推送时间段内
function P:IsCanPushNotifications(pushTime)

	-- 允许推送时间
	local pushAllowTime = string.split(tpl_constdata[PUSH_ALLOW_TIME_KEY], ',')
	local startTimeStrs = string.split(pushAllowTime[1], ':')
	local stopTimeStrs = string.split(pushAllowTime[2], ':')

	-- 推送时间
	local pushTimeStrs = string.split(os.date("%H:%M:%S", pushTime), ':')

	pushTimeStrs[1] = tonumber(pushTimeStrs[1])
	startTimeStrs[1] = tonumber(startTimeStrs[1])
	stopTimeStrs[1] = tonumber(stopTimeStrs[1])

	-- 时
	if pushTimeStrs[1] > startTimeStrs[1] and pushTimeStrs[1] < stopTimeStrs[1] then
		return true
	end

	pushTimeStrs[2] = tonumber(pushTimeStrs[2])
	startTimeStrs[2] = tonumber(startTimeStrs[2])

	-- 时相等判断分
	if pushTimeStrs[1] == startTimeStrs[1] and pushTimeStrs[2] > startTimeStrs[2] then
		return true
	end

	stopTimeStrs[2] = tonumber(stopTimeStrs[2])

	if pushTimeStrs[1] == stopTimeStrs[1] and pushTimeStrs[2] < stopTimeStrs[2] then
		return true
	end

	pushTimeStrs[3] = tonumber(pushTimeStrs[3])
	startTimeStrs[3] = tonumber(startTimeStrs[3])

	-- 时分相等判断秒
	if pushTimeStrs[1] == startTimeStrs[1] and pushTimeStrs[2] == startTimeStrs[2] and pushTimeStrs[3] >= startTimeStrs[3] then
		return true
	end

	stopTimeStrs[3] = tonumber(stopTimeStrs[3])

	if pushTimeStrs[1] == stopTimeStrs[1] and pushTimeStrs[2] == stopTimeStrs[2] and pushTimeStrs[3] <= stopTimeStrs[3] then
		return true
	end

	return false
end

-- 计算推送时间
function P:CalculateFireTime(pushType, param)

	local pushTime = 0

	if pushType == NOTIFICATION_TYPE.LIFE_FULL then
		pushTime = self:CalHpFullTime()

	elseif pushType == NOTIFICATION_TYPE.LIFE_ADD then
		pushTime = self:CalHpNextRecoverTime()

	elseif pushType == NOTIFICATION_TYPE.ASSIGN_TIME then
		pushTime = self:CalAssignPushTime(param)
	end

	-- 是否在可推送时间内
	if self:IsCanPushNotifications(pushTime) then
		-- 前面计算出来的是推送时间，需要减去当前服务器时间获得触发时间
		return pushTime - bee.getServerTime()
	else
		return 0
	end
end

-- 计算每个类型今日可推送次数
function P:CalculateNotificationsAllowTimes(refreshTime, pushType, times)
	if not CU.PlayerPrefs.HasKey(NOTIFICATION_TYPE_STORE_NAME_STR .. pushType) then
		return times
	end

	local value = LocalStore:getStringForKey(NOTIFICATION_TYPE_STORE_NAME_STR .. pushType)

	local notificationValue = string.split(value, '_')

	if notificationValue[1] and notificationValue[2] then

		-- 同一天
		if math.abs(tonumber(notificationValue[1]) - refreshTime) < 100 then
			return times - tonumber(notificationValue[2])
		else
			return times
		end
	else
		return times
	end
end

function P:GetTimeStr(timeStr)
	return string.format("%s %s", os.date("%Y-%m-%d", bee.getServerTime()), timeStr)
end

function P:SendUpdateNotifyStatusReq()
end

function P:SetIsNotifications(status)
	LocalStore:setBoolForKey("is_show_notifications", status)

	-- 上报服务器
	self:SendUpdateNotifyStatusReq()
end

function P:GetIsNotifications()
	if not CU.PlayerPrefs.HasKey(IS_NOTIFICATIONS_KEY) then
		-- 默认推送
		LocalStore:setBoolForKey(IS_NOTIFICATIONS_KEY, true)
	end

	return LocalStore:getBoolForKey(IS_NOTIFICATIONS_KEY)
end

-- 计算推送条数
function P:CalculatePushNotifications()
	if NOT_USE_FIREBASE then return end
	-- 判断是否需要计算推送,使用firebase的不需要推送
	if CS.MobileNotificationsMgr.Instance:IsCanUseFirebase() then
		return
	end

	-- 设置选项
	local is_show = LocalStore:getBoolForKey(IS_NOTIFICATIONS_KEY)
	if not is_show then
		return
	end

	-- 今日刷新时间戳
	local refreshTime = TimeLib.string2time(self:GetTimeStr(PUSH_REFRESH_TIME))

	local notificationsList = {}

	-- 遍歷配置表，計算所有需要推送的消息
	for _, cfg in pairs(tpl_systemPush) do

		if not notificationsList[cfg.pushType] then
			notificationsList[cfg.pushType] = {}
		end

		-- -- 当前类型剩余推送次数
		-- local notificationResidueDegree = self:CalculateNotificationsAllowTimes(refreshTime, cfg.pushType, cfg.times)

		-- -- 判断当前类型是否还有推送次数
		-- if notificationResidueDegree > 0 then

			local fireTime = self:CalculateFireTime(cfg.pushType, cfg.param)

			-- 判断是否会触发该事件
			if fireTime > 0 then

				local notification = {}
				notification.title = LanguageManager:getString(NOTIFICATION_TITLE_KEY)
				notification.text = LanguageManager:getString(cfg.text)
				notification.fireTime = fireTime
				notification.priority = cfg.priority
				notification.pushType = cfg.pushType

				local isCanPush, highFireTimeIndex, lowPriorityIndex

				-- 根据时间和优先级判断是否可以推送
				isCanPush, lowPriorityType, lowPriorityIndex = self:CalIsCanPushByPriority(notificationsList, notification)
				if lowPriorityType and lowPriorityIndex then
					table.remove(notificationsList[lowPriorityType], lowPriorityIndex)
				end

				-- -- 根据限制次数判断是否可以推送
				-- isCanPush, highFireTimeIndex = self:CalIsCanPushByTimes(notificationsList[cfg.pushType], notification, notificationResidueDegree)
				-- if highFireTimeIndex then
				-- 	table.remove(notificationsList[cfg.pushType], highFireTimeIndex)
				-- end

				if isCanPush then
					table.insert(notificationsList[cfg.pushType], notification)
				end
			-- end
		end
	end

	-- 推送消息
	for _, notificationTypeList in pairs(notificationsList) do
		for _, notification in pairs(notificationTypeList) do
			CS.MobileNotificationsMgr.Instance:PushNotification(notification.title, notification.text, notification.fireTime, notification.pushType)
		end
	end
end

-- 判断是否足够存入次数（触发时间短的先触发，并占用一次次数）
function P:CalIsCanPushByTimes(notificationsTypeList, newNotification, residueDegree)

	-- 已存入的同类型推送次数
	local notificationTimes = #notificationsTypeList

	if notificationTimes < residueDegree then
		return true
	end

	local highFireTimeIndex = 0

	-- 取触发时间短的，因为短的会比触发时间长的先触发，从而先占用一次次数
	for index, notification in ipairs(notificationsTypeList) do
		if newNotification.fireTime < notification.fireTime then
			highFireTimeIndex = index
		end
	end

	if highFireTimeIndex <= 0 then
		return false
	else
		return true, highFireTimeIndex
	end
end

-- 判断是否为相同时间，相同时间触发的只保留优先级高的
function P:CalIsCanPushByPriority(notificationsList, newNotification)
	
	for type, notificationsTypeList in pairs(notificationsList) do
		for index, notification in pairs(notificationsTypeList) do
			-- 触发时间相等的，只保留优先级最高的一条
			if notification.fireTime == newNotification.fireTime then
				if newNotification.priority < notification.priority then
					return true, type, index
				else
					return false
				end
			end
		end
	end

	return true
end

-- 检查是否有推送附带消息
function P:CheckNotificationIntentData()
	if self.isLog then
		return
	end
	if NOT_USE_FIREBASE then return end

	local extrasData = CS.MobileNotificationsMgr.Instance:getNotificationIntentData()
	if extrasData and extrasData ~= "" then
		self.isLog = true
	end
end

return P