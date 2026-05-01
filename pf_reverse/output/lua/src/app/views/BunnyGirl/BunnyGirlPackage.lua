local P = class("BunnyGirlPackage", UiDialog)

function P:onAwake()
	local Pannel = self:find("AnimRoot/Center/Pannel")
	self.TimeText = self:find("Time/TimeText", Pannel)
	self.PackageScrollList = self:find("PackageScrollList", Pannel)
	self.Item1 = self:find("PackageScrollList/Item1", Pannel)
	self.Item1:SetActive(false)

	self.CloseButton = self:find("CloseButton", Pannel)
	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)

	self._timeTags = {}
end

function P:onStart()
	self.packageList = UiListEx:create(self.PackageScrollList)
	self.packageList:setCreateFunc(function()
		return CU.GameObject.Instantiate(self.Item1)
	end)
	self.packageList:setRefreshFunc(function(data, item, isInit, index)
		self:setItemPackage(item, data, isInit, index)
	end)
	self.packageList:setWidth(300)

	local data = ShopModel:getShopPackageList(SHOP_TYPE.activity_gifts)
	self.packageList:setDatas(data)

	-- 活动倒计时
	local endTime = ActivityManager:getActivityEndTime(ActivityId.Theme, 10004)
	if endTime > 0 then
		local leftTime = endTime - bee.getServerTime()
		if leftTime > 0 then
			bee.setText(self.TimeText, ShopModel:getShopTimeText(leftTime))
			self:schedule(1, function()
				leftTime = leftTime - 1
				if leftTime > 0 then
					bee.setText(self.TimeText, ShopModel:getShopTimeText(leftTime))
				else
					bee.setText(self.TimeText, _T("LAB_BACKPACK_DES_21"))
				end
			end, item)
		else
			bee.setText(self.TimeText, _T("LAB_BACKPACK_DES_21"))
		end
	end
end

function P:refreshUI()
	if not self.packageList then
		return
	end
	local data = ShopModel:getShopPackageList(SHOP_TYPE.activity_gifts)
	self.packageList:setDatas(data)
end

function P:setItemPackage(item, data, isInit, index)
	local Ani_root = self:find("Ani_root", item)
	local PackageBg = self:find("PackageBg", Ani_root)
	local PackageNameText = self:find("PackageNameText", Ani_root)
	local LimitText = self:find("LimitText", Ani_root)
	local BuyButton = self:find("BuyButton", Ani_root)
	local BuyText = self:find("BuyButton/BuyText", Ani_root)
	local PackageIcon = self:find("PackageIcon/PackageIcon", Ani_root)
	local SoldOut = self:find("SoldOut", Ani_root)

	if isInit then
        self:once(0.1 * (index - 1), function()
            Ani_root:SetActive(true)
            self:playAnimator("UI_1_BunnyGirItem", Ani_root)
        end)
        Ani_root:SetActive(false)
    else
        Ani_root:SetActive(true)
        self:playAnimator("UI_1_TaskView_item_idle", Ani_root)
    end

	if self._timeTags[item] then
		scheduler:removeTag(self._timeTags[item])
	end

	SoldOut:SetActive(data.soldOut)
	BuyButton:SetActive(not data.soldOut)

	local cfg = data.cfg
	bee.setText(PackageNameText, _T(cfg.name))
	bee.setIconInAtlas(PackageIcon, cfg.icon)

	if not data.soldOut then
		local pidCfg = ShopModel:getPidData(cfg.buy_id)
		bee.setText(BuyText, ShopModel:getPriText(pidCfg))
	end

	if cfg.limit_type == SHOP_LIMIT_TYPE.DAILY then
		LimitText:SetActive(true)
		bee.setText(LimitText, _F("LAB_SHOP_COMMON_42", data.buyCount, cfg.limit_count))
	elseif cfg.limit_type == SHOP_LIMIT_TYPE.WEEKLY then
		LimitText:SetActive(true)
		bee.setText(LimitText, _F("LAB_SHOP_COMMON_43", data.buyCount, cfg.limit_count))
	elseif cfg.limit_type == SHOP_LIMIT_TYPE.MONTHLY then
		LimitText:SetActive(true)
		bee.setText(LimitText, _F("LAB_SHOP_COMMON_44", data.buyCount, cfg.limit_count))
	elseif cfg.limit_type == SHOP_LIMIT_TYPE.PERMANENT then
		LimitText:SetActive(true)
		bee.setText(LimitText, _F("LAB_SHOP_COMMON_45", data.buyCount, cfg.limit_count))
	else
		LimitText:SetActive(false)
	end

	local buyFunc = function()
		if data.soldOut then
			UiManager:showToast(_T("LAB_SHOP_COMMON_9"))
			return
		end
		Game:playSound("ui_button_confirm")
		local cfg = data.cfg
		if cfg.time_end and (cfg.time_end - bee.getServerTime()) < 0 then
			UiManager:showToast(_T("LAB_SHOP_COMMON_10"))
			self:refreshUI()
			return
		end
		if cfg.shop_type == SHOP_TYPE.shop_gifts then
			bee.logEvent("shop-goods-tap", cfg.shop_type, cfg.id)
			ShopModel:pay(cfg)
		else
			UiManager:showUI("ShopPurchasePackage", {data = data})
		end
	end

	bee.removeAllClick(BuyButton)
	bee.addClick2(BuyButton, function()
		buyFunc()
	end)

	bee.removeAllClick(item)
	bee.addClick2(item, function()
		buyFunc()
	end)
end

function P:evt_updateShopLimit()
	self:refreshUI()
end

return P