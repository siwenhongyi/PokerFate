---------------------------------------------------------------------
-- wam (C) CompanyName, All Rights Reserved
-- Created by: Quer
-- Date: 2024-03-19 15:29:12
-- 新广告变现系统（与原广告系统不冲突）
---------------------------------------------------------------------

---@class AdvertBtn
local P = class("AdvertBtn")

-- local M = class("AdvertInfo")
-- function M:ctor(advertId)
-- 	self._node = nil 			-- 绑定的节点
-- 	self._onCompleteCb = nil 	-- 完成回调
-- 	self._onCloseCb = nil 		-- 关闭回调
-- 	self._onFailCb = nil
-- 	self._onClickBtnCb = nil    -- 点击按钮回调
-- 	self._curAdvertId = advertId 	-- 当前广告 id
-- 	self._rewardedCompleted = false

-- 	if tpl_advertising[advertId].type == 1 then
-- 		bee.logEvent("ad_exposure_new", advertId, tpl_advertising[advertId].type)
-- 	end
-- end

-- local _advertInfos = {}

-- function _getAdEcpmInfo(info)
-- 	local ad_revenue,ad_ecpm,lt_revenue = nil, nil, nil
-- 	if info then
-- 		local data = "return {" .. string.split(info, "{")[2]
-- 		if data then
-- 			local d = loadstring(data)
-- 			if d then
-- 				d = d()
-- 				if d then
-- 					ad_revenue,ad_ecpm,lt_revenue = d.revenue,d.encryptedCPM,d.lifetimeRevenue
-- 				end
-- 			end
-- 		end
-- 	end
-- 	return ad_revenue,ad_ecpm,lt_revenue
-- end

-- --激励

-- bee.on("evt_RewardedOnAdShowed", function(info)
-- 	local advertInfo = _advertInfos[AdvertType.Rewarded]
-- 	if advertInfo then
-- 		bee.logEvent("ad_impressions", advertInfo._curAdvertId, AdvertType.Rewarded)
-- 	end
-- end)

-- bee.on("evt_RewardedVideoOpened", function(info)
-- 	local advertInfo = _advertInfos[AdvertType.Rewarded]
-- 	if advertInfo then
-- 		LogEx:log_ad_log("show", advertInfo._curAdvertId, AdvertType.Rewarded, nil, _getAdEcpmInfo(info))
-- 		LogEx:log_ad_log("imp", advertInfo._curAdvertId, AdvertType.Rewarded, nil, _getAdEcpmInfo(info))
-- 		bee.logEvent("ad_over", PlayerModel:getCurLevel(), advertInfo._curAdvertId)
-- 	end
-- end)

-- bee.on("evt_RewardedVideoClosed", function(info)
-- 	local advertInfo = _advertInfos[AdvertType.Rewarded]
-- 	if advertInfo then
-- 		if advertInfo._rewardedCompleted then
-- 			LogEx:log_ad_log("done", advertInfo._curAdvertId, AdvertType.Rewarded, nil, _getAdEcpmInfo(info))
-- 		else
-- 			LogEx:log_ad_log("quit", advertInfo._curAdvertId, AdvertType.Rewarded, nil, _getAdEcpmInfo(info))
-- 		end
-- 		print("[Advert] motivational_advertising_close = " .. advertInfo._curAdvertId)
-- 		bee.logEvent("motivational_advertising_close", advertInfo._curAdvertId)
-- 		if (not advertInfo._checkSelf or (advertInfo._checkSelf and not bee.isNull(advertInfo._node))) and advertInfo._onCloseCb then
-- 			advertInfo._onCloseCb(advertInfo._rewardedCompleted)
-- 		end
-- 		advertInfo._onCloseCb = nil
-- 		CS.IronSourceHelper.Instance:LoadRewardedVideo()
-- 	end
-- end)

-- bee.on("evt_RewardedVideoClicked", function(info)
-- 	local advertInfo = _advertInfos[AdvertType.Rewarded]
-- 	if advertInfo then
-- 		LogEx:log_ad_log("inad_click", advertInfo._curAdvertId, AdvertType.Rewarded, nil, _getAdEcpmInfo(info))
-- 		print("[Advert] motivational_advertising_clickLink = " .. advertInfo._curAdvertId)
-- 		bee.logEvent("motivational_advertising_clickLink", advertInfo._curAdvertId)
-- 		bee.logEvent("ad_return", advertInfo._curAdvertId, AdvertType.Rewarded)
-- 	end
-- end)

-- bee.on("evt_RewardedVideoCompleted", function(info)
-- 	local advertInfo = _advertInfos[AdvertType.Rewarded]
-- 	if advertInfo then
-- 		print("[Advert] motivational_advertising_watchComplete = " .. advertInfo._curAdvertId, info)
-- 		bee.logEvent("motivational_advertising_watchComplete", advertInfo._curAdvertId)
-- 		bee.logEvent("ad_done", advertInfo._curAdvertId)
-- 		if (not advertInfo._checkSelf or (advertInfo._checkSelf and not bee.isNull(advertInfo._node))) and advertInfo._onCompleteCb then
-- 			advertInfo._onCompleteCb()
-- 		end
-- 		advertInfo._onCompleteCb = nil
-- 		advertInfo._rewardedCompleted = true
-- 		CS.IronSourceHelper.Instance:LoadRewardedVideo()

-- 		LogEx:log_ad_log("reward", advertInfo._curAdvertId, AdvertType.Rewarded, nil, _getAdEcpmInfo(info))

-- 		local ad_revenue, ad_ecpm = _getAdEcpmInfo(info)
-- 		ad_revenue = math.floor(ad_revenue * 1000000)
-- 		bee.logEvent("ad_sdk_return", advertInfo._curAdvertId, AdvertType.Rewarded, ad_revenue, ad_ecpm)

-- 		bee.emit("evt_RewardedCompleted")
-- 		bee.emit("evt_advert_revenue", {revenue = ad_revenue, ecpm = ad_ecpm})
-- 	end
-- end)

-- ---banner

-- bee.on("evt_BannerOnAdShowed", function(info)
-- 	local advertInfo = _advertInfos[AdvertType.Banner]
-- 	print("=== gggg evt_BannerOnAdShowed", advertInfo, AdvertType.Banner)
-- 	if advertInfo then
		
-- 		LogEx:log_ad_log("imp", advertInfo._curAdvertId, AdvertType.Banner, nil, _getAdEcpmInfo(info))
-- 		print("[Advert] banner_advertising_showCounts = " .. advertInfo._curAdvertId)
-- 		bee.logEvent("banner_advertising_showCounts", advertInfo._curAdvertId)
-- 		bee.logEvent("ad_impressions", advertInfo._curAdvertId, AdvertType.Banner)

-- 		local ad_revenue, ad_ecpm = _getAdEcpmInfo(info)
-- 		ad_revenue = math.floor(ad_revenue * 1000000)
-- 		bee.logEvent("ad_sdk_return", advertInfo._curAdvertId, AdvertType.Banner, ad_revenue, ad_ecpm)
-- 		bee.emit("evt_advert_revenue", {revenue = ad_revenue, ecpm = ad_ecpm})
-- 	end
-- end)

-- bee.on("evt_BannerOnAdHided", function(info)
-- 	local advertInfo = _advertInfos[AdvertType.Banner]
-- 	if advertInfo then
-- 		LogEx:log_ad_log("close", advertInfo._curAdvertId, AdvertType.Banner, nil, _getAdEcpmInfo(info))
-- 	end
-- end)

-- bee.on("evt_BannerOnAdClicked", function()
-- 	local advertInfo = _advertInfos[AdvertType.Banner]
-- 	if advertInfo then
-- 		print("[Advert] evt_BannerOnAdClicked = " .. advertInfo._curAdvertId)
-- 		bee.logEvent("banner_advertising_clickCounts", advertInfo._curAdvertId)
-- 		bee.logEvent("ad_return", advertInfo._curAdvertId, AdvertType.Banner)
-- 	end
-- end)


-- --插屏
-- bee.on("evt_InterstitialOnAdShowed", function(info) 
-- 	local advertInfo = _advertInfos[AdvertType.InsertScreen]
-- 	if advertInfo then
-- 		bee.logEvent("ad_impressions", advertInfo._curAdvertId, AdvertType.InsertScreen)
-- 	end
-- end)

-- bee.on("evt_InterstitialOnAdShowSucceeded", function(info) 
-- 	local advertInfo = _advertInfos[AdvertType.InsertScreen]
-- 	if advertInfo then
-- 		bee.logEvent("insert_screen_interface", advertInfo._curAdvertId)
-- 		LogEx:log_ad_log("imp", advertInfo._curAdvertId, AdvertType.InsertScreen, nil, _getAdEcpmInfo(info))
-- 	end
-- end)

-- bee.on("evt_InterstitialOnAdShowFailed", function(info) 
-- 	local advertInfo = _advertInfos[AdvertType.InsertScreen]
-- 	if advertInfo then
-- 		if advertInfo._onFailCb then
-- 			advertInfo._onFailCb()
-- 		end
-- 		advertInfo._onFailCb = nil
-- 	end
-- end)

-- bee.on("evt_InterstitialOnAdClicked", function() 
-- 	local advertInfo = _advertInfos[AdvertType.InsertScreen]
-- 	if advertInfo then
-- 		bee.logEvent("insert_screen_clickLink", advertInfo._curAdvertId)
-- 		bee.logEvent("ad_return", advertInfo._curAdvertId, AdvertType.InsertScreen)
-- 	end
-- end)

-- bee.on("evt_InterstitialOnAdClosed", function(info) 
-- 	local advertInfo = _advertInfos[AdvertType.InsertScreen]
-- 	if advertInfo then
-- 		LogEx:log_ad_log("done", advertInfo._curAdvertId, AdvertType.InsertScreen, nil, _getAdEcpmInfo(info))
-- 		print("[Advert] insert_screen_watchComplete = " .. advertInfo._curAdvertId)
-- 		bee.logEvent("insert_screen_watchComplete", advertInfo._curAdvertId)
-- 		if advertInfo._onCompleteCb then
-- 			advertInfo._onCompleteCb()
-- 		end
-- 		advertInfo._onCompleteCb = nil
-- 		local ad_revenue, ad_ecpm = _getAdEcpmInfo(info)
-- 		ad_revenue = math.floor(ad_revenue * 1000000)
-- 		bee.logEvent("ad_sdk_return", advertInfo._curAdvertId, AdvertType.InsertScreen, ad_revenue, ad_ecpm)
-- 		CS.IronSourceHelper.Instance:LoadInterstitial()
-- 	end
-- end)

-- ---@param auto bool 无需点击，直接触发
-- ---@param checkSelf bool 回调触发时检查自身是否存在
-- function P:ctor(node, advertId, auto, checkSelf)
--     local oldAdvertId = self.curAdvertId
--     self.curAdvertId = advertId
-- 	self.advertCfg = tpl_advertising[self.curAdvertId]
-- 	self.advertType = self.advertCfg.type
-- 	self.auto = auto
-- 	checkSelf = checkSelf == nil and true or checkSelf
	
-- 	if _advertInfos[self.advertType] then
-- 		_advertInfos[self.advertType] = nil
-- 	end
-- 	_advertInfos[self.advertType] = M:create(advertId)
-- 	_advertInfos[self.advertType]._node = node
-- 	_advertInfos[self.advertType]._checkSelf = checkSelf

--     self.videoClick = false
--     if oldAdvertId ~= self.curAdvertId and self.advertCfg then
--         LogEx:log_ad_log("exposure", self.advertCfg.id, self.advertType)
--     end
-- 	self:prepareVideo()

-- 	if auto then
-- 		bee.once(0.2, function() 
-- 			self:onAdvertBtnClick()
-- 		end)
-- 	else
-- 		bee.removeAllClick(node)
-- 		bee.AddClick(node, function()
-- 			self:onAdvertBtnClick()
-- 		end)
-- 	end
-- end

-- --是否显示该按钮逻辑不在这里
-- function P:prepareVideo()
-- 	if self.advertCfg.type == AdvertType.Rewarded then
-- 		CS.IronSourceHelper.Instance:LoadRewardedVideo()
-- 	elseif self.advertCfg.type == AdvertType.Banner then
-- 		CS.IronSourceHelper.Instance:LoadBanner(2, "DefaultRewardedVideo")
-- 	elseif self.advertCfg.type == AdvertType.InsertScreen then
-- 		CS.IronSourceHelper.Instance:LoadInterstitial()
-- 	end
-- end

-- --按钮点击事件
-- function P:addClickCb(finishedCb)
-- 	self.videoClick = finishedCb
--     if _advertInfos[self.advertType] then
-- 		_advertInfos[self.advertType]._onClickBtnCb = finishedCb
-- 	end
-- end

-- --视频完成事件
-- function P:addCompleteCb(finishedCb)
-- 	if _advertInfos[self.advertType] then
-- 		_advertInfos[self.advertType]._onCompleteCb = finishedCb
-- 	end
-- end

-- function P:addFailCb(finishedCb)
-- 	if _advertInfos[self.advertType] then
-- 		_advertInfos[self.advertType]._onFailCb = finishedCb
-- 	end
-- end

-- --视频关闭事件
-- function P:addCloseCb(finishedCb)
-- 	if _advertInfos[self.advertType] then
-- 		_advertInfos[self.advertType]._onCloseCb = finishedCb
-- 	end
-- end

-- function P:onAdvertBtnClick()
-- 	bee.logEvent("ad_click_new", self.advertCfg.id, self.advertType)
-- 	if self.advertCfg.type == AdvertType.Rewarded then
-- 		LogEx:log_ad_log("click", self.advertCfg.id, self.advertType)
-- 		bee.logEvent("motivational_advertising_clickCounts", self.advertCfg.id)
-- 		if _advertInfos[self.advertType] then
-- 			_advertInfos[self.advertType]._rewardedCompleted = false
-- 		end
-- 	end
--     if self.videoClick then
--         local bool = self.videoClick()
-- 		if bool then
-- 			return
-- 		end
--     end

-- 	if AdvertModel:checkAdvertNotAvailable(self.advertCfg.type) then
-- 		if not self.auto then
-- 			UiManager:showToast(_T("LAB_NO_VIDEO"), bee.v3(0, 0))
-- 		end
-- 		if self.advertCfg.type == AdvertType.Rewarded or self.advertCfg.type == AdvertType.InsertScreen then
-- 			self:prepareVideo()
-- 		end
--         return
-- 	end

--     if self.advertCfg then
-- 		if self.advertCfg.type == AdvertType.Rewarded then
-- 			bee.logEvent("motivational_advertising_playCounts", self.advertCfg.id)
-- 		end
--     end

-- 	if self.advertCfg.type == AdvertType.Rewarded then
-- 		CS.IronSourceHelper.Instance:ShowRewardedVieo("DefaultRewardedVideo")
-- 	elseif self.advertCfg.type == AdvertType.Banner then
-- 		CS.IronSourceHelper.Instance:ShowBanner()
-- 	elseif self.advertCfg.type == AdvertType.InsertScreen then
-- 		CS.IronSourceHelper.Instance:ShowInterstitial("DefaultInterstitial")
-- 	end
-- end

-- function P:onDestroy()
--     P.super.onDestroy(self)
-- end

return P
