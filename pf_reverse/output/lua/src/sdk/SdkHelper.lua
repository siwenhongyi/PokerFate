local P = {
}
SdkHelper = P

local function guid()
    local seed={'1','2','3','4','5','6','7','8','9','a','b','c','d','e','f','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w','x','y','z'}
    local tb={}
    for i=1,32 do
        table.insert(tb,seed[math.random(1,#seed)])
    end
    local sid=table.concat(tb)
    return string.format('%s-%s-%s-%s-%s',
        string.sub(sid,1,8),
        string.sub(sid,9,12),
        string.sub(sid,13,16),
        string.sub(sid,17,20),
        string.sub(sid,21,32)
    )
end

function P:isTestB()
	return self:getABFlag() == "B"
end

function P:getABFlag()
	local flag = LocalStore:getStringForKey("ABFlag")
	if not flag or "" == flag then
		local deviceCrc=CS.Utils.GetCRC32Str(self:getDeviceID())
		if tonumber(deviceCrc)%100 < 50 then
			flag = "A"
		else
			flag = "B"
		end
		LocalStore:setStringForKey("ABFlag", flag)
	end
	return flag
end

function P:changeABFlag(flag)
	LocalStore:setStringForKey("ABFlag", flag)
	if GameABTestManager then
		GameABTestManager:setTestType(flag)
	end
end

function P:getDeviceID()
    local id = LocalStore:getStringForKey("device_id")
    if not id or "" == id or id == "00000000-0000-0000-0000-000000000000" or id == "02:00:00:00:00:00" then
        id = CS.SdkHelper.getDeviceID()
        if not id or "" == id or id == "00000000-0000-0000-0000-000000000000" or id == "02:00:00:00:00:00" then
            id = CU.SystemInfo.deviceUniqueIdentifier--guid()
			if not id or "" == id or id == "00000000-0000-0000-0000-000000000000" or id == "02:00:00:00:00:00" then
				id = guid()
			end
        end
        LocalStore:setStringForKey("device_id", id)
    end
    return id
end

function P:adjustLaunched()
	CS.SdkHelper.AdjustLaunched(not bee.isRelease)
end

function P:getAdjustId()
	local adjustId = CS.SdkHelper.GetAdjustID()--先拿最新的没有再拿缓存比较合适
	if string.len(adjustId) < 1 then
		SdkModel:getAdjustCache()
	end
	print("getAdjustId",adjustId)
    return adjustId
end


--跳转谷歌商店评价
function P:jumpGoogleReview()
	CS.SdkHelper.JumpGoogleReview()
end


function P:getOs()
	local os = CU.SystemInfo.operatingSystem
	if os == nil or os == "" then
		os = CS.SdkHelper.getOs()
	end
	return os
end

function P:getDeviceModel()
	return CU.SystemInfo.deviceModel
end

function P:getDeviceType()
	if bee.isAndroid then
		return CS.SdkHelper.isPad() and 5 or 2
	elseif bee.isIos then
		return CS.SdkHelper.isPad() and 4 or 1
	else
		return 3
	end
end

function P:getToken()
	local token = nil
	if bee.checkVersion("1.2.12") then
		token = CS.ThirdManager.Instance:getToken()
	end
	return token
end

function P:isBindingAccount()
	return self._isBinding
end

function P:setIsBindingAccount(flag)
	self._isBinding = flag
end

function P:sentAdjustEvent(name, context)
	print("[Adjust sendAdjustEvent]", name, context)
	if context then
		CS.SdkHelper.SentAdjustEvent(name, context)
		-- CS.SdkHelper.FBLogEvent(name, context)
	else
		CS.SdkHelper.SentAdjustEvent(name)
		-- CS.SdkHelper.FBLogEvent(name)
	end
end

function P:sendFbEvent(name, context)
	if context then
		CS.SdkHelper.FBLogEvent(name, context)
	else
		CS.SdkHelper.FBLogEvent(name)
	end
end

function P:sendFirebaseEvent(name)
	CS.SdkHelper.FirebaseLogEvent(name)
end

function P:vibrate(dts)
	CS.SdkHelper.vibrate(dts)
end

function P:vibrate2(dts, amplitudes)
	CS.SdkHelper.vibrate2(dts, amplitudes)
end

function onAppReview(success)
	print("onAppReview", success)
	if success then
		Net:post("/game/appComment", {t = 1}, function()
		end)
	end
	if SdkHelper._reviewTask then
		SdkHelper._reviewTask:stop()
		SdkHelper._reviewTask = nil
	end
end

function P:startAppReview()
	print("[SdkHelper] startAppReview")
	if bee.isPc then
		if not bee.isEditor then
			return
		end
	elseif bee.isIos then
		return
	end
	Net:post("/game/getAppComment", {t = 1}, function(data)
		local flag = true
		if data and 0 == data.code then
			local ct = bee.getServerTime()
			if not data.list or 0 == #data.list then
			else
				table.sort(data.list)
				local lastEt = ct - data.list[#data.list]
				if lastEt <= 7 * 86400 then
					flag = false
				elseif lastEt > 365 * 86400 then
					flag = true
				else
					if data.list[#data.list - 2] and ct - data.list[#data.list - 2] <= 365 * 86400 then
						flag = false
					end
				end
			end
		end

		print("==== ggggggggg /game/getAppComment", json.encode(data), flag)
		if flag then
			self._reviewTask = bee.addTaskFunc(function()
				print("[SdkHelper] reviewTask startAppReview")
				if bee.isAndroid then
					CS.GoogleMgr.startAppReview(bee.isTest)
				elseif bee.isIos then
					CS.GoogleMgr.startAppReview(bee.isTest)
					bee.once(1, function()
						onAppReview(true)
					end)
				else
					bee.once(1, function()
						onAppReview(true)
					end)
				end
			end, 10, nil, LOBBY_POP_PRIORITY.ReviewScore)
			bee.runTask()
		end
	end)
end

