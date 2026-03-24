local P = class("ShopPackage", UiBase)

function P:onAwake()
	self.PackageScrollList = self:find("PackageScrollList")
	self.ItemPackage = self:find("ItemPackage")
	self.ItemPackage:SetActive(false)

	self._itemLists = {}
	self._timeTags = {}
end

function P:onStart()
	self.shop_type = self._params.shop_type

	self.packageList = UiListEx:create(self.PackageScrollList)
	self.packageList:setCreateFunc(function()
		return CU.GameObject.Instantiate(self.ItemPackage)
	end)
	self.packageList:setRefreshFunc(function(data, item, isInit, index)
		self:setItemPackage(item, data, isInit, index)
	end)
	self.packageList:setWidth(460)

	local data = ShopModel:getShopPackageList(self.shop_type)
	self.packageList:setDatas(data)

	-- 任务进度-查看商城礼包
	TaskModel:reportTask(TaskType.CheckView, TaskTargetId.ShopPackage)
end

function P:setItemPackage(item, data, isInit, index)
	local Ani_root = self:find("Ani_root", item)
	local PriceText = self:find("PriceText", Ani_root)
	local SoldOut = self:find("SoldOut", Ani_root)

	if isInit then
        self:once(0.1 * (index - 1), function()
            Ani_root:SetActive(true)
            self:playAnimator("UI_2_ShopPackage_item", Ani_root)
        end)
        Ani_root:SetActive(false)
    else
        Ani_root:SetActive(true)
        self:playAnimator("UI_1_TaskView_item_idle", Ani_root)
    end
	
	self:setItem(item, data)

	if data.soldOut then
		SoldOut:SetActive(true)
		PriceText:SetActive(false)
	else
		SoldOut:SetActive(false)
		PriceText:SetActive(true)
	end

	bee.removeAllClick(item)
	bee.addClick2(item, function()
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
	end)
end

function P:setItem(item, data)
	local Ani_root = self:find("Ani_root", item)
	local PackageBg = self:find("PackageBg", Ani_root)
	local PackageIcon = self:find("PackageIcon", Ani_root)
	local NameText = self:find("NameText", Ani_root)
	local TagBg = self:find("TagBg", Ani_root)
	local TagText = self:find("TagText", TagBg)
	local TimeBg = self:find("TimeBg", Ani_root)
	local TimeText = self:find("TimeText", TimeBg)
	local TextBg = self:find("TextBg", Ani_root)
	local ItemText = self:find("TextBg/ItemText", Ani_root)
	local LimitText = self:find("LimitText", Ani_root)
	local PriceText = self:find("PriceText", Ani_root)
	local SoldOut = self:find("SoldOut", Ani_root)

	if self._timeTags[item] then
		scheduler:removeTag(self._timeTags[item])
	end

	local cfg = data.cfg
	bee.setText(NameText, _T(cfg.name))
	bee.setIconInAtlas(PackageIcon, cfg.icon)
	if not data.soldOut then
		if cfg.goods_bg == 1 then
			bee.setIcon(PackageBg, "shop_gacha_item_bg_02", "Shop")
		else
			bee.setIcon(PackageBg, "shop_gacha_item_bg_01", "Shop")
		end
	end

	if cfg.shop_type == SHOP_TYPE.shop_gifts then
		TextBg:SetActive(true)
		local propCfg = tpl_props[cfg.props[1]]
		if cfg.props[2] > 1 then
			bee.setText(ItemText, _T(propCfg.name) .. " x" .. cfg.props[2])
		else
			bee.setText(ItemText, _T(propCfg.name))
		end
	else
		TextBg:SetActive(false)
	end

	if cfg.tag_text then
		TagBg:SetActive(true)
		bee.setText(TagText, _T(cfg.tag_text))
	else
		TagBg:SetActive(false)
	end

	-- 倒计时
	if cfg.time_end then
		TimeBg:SetActive(true)

		local leftTime = cfg.time_end - bee.getServerTime()
		if leftTime > 0 then
			bee.setText(TimeText, ShopModel:getShopTimeText(leftTime))
			self._timeTags[item] = bee.schedule(1, function()
				leftTime = leftTime - 1
				if leftTime > 0 then
					bee.setText(TimeText, ShopModel:getShopTimeText(leftTime))
				else
					bee.setText(TimeText, _T("LAB_BACKPACK_DES_21"))
				end
			end, item)
		else
			bee.setText(TimeText, _T("LAB_BACKPACK_DES_21"))
		end
	else
		TimeBg:SetActive(false)
	end

	if cfg.limit_type == SHOP_LIMIT_TYPE.DAILY then
		LimitText:SetActive(true)
		bee.setText(LimitText, _T("LAB_SHOP_COMMON_11") .. ":" .. data.buyCount .. "/" .. cfg.limit_count)
	elseif cfg.limit_type == SHOP_LIMIT_TYPE.WEEKLY then
		LimitText:SetActive(true)
		bee.setText(LimitText, _T("LAB_SHOP_COMMON_12") .. ":" .. data.buyCount .. "/" .. cfg.limit_count)
	elseif cfg.limit_type == SHOP_LIMIT_TYPE.MONTHLY then
		LimitText:SetActive(true)
		bee.setText(LimitText, _T("LAB_SHOP_COMMON_13") .. ":" .. data.buyCount .. "/" .. cfg.limit_count)
	elseif cfg.limit_type == SHOP_LIMIT_TYPE.PERMANENT then
		LimitText:SetActive(true)
		bee.setText(LimitText, _T("LAB_SHOP_COMMON_14") .. ":" .. data.buyCount .. "/" .. cfg.limit_count)
	else
		LimitText:SetActive(false)
	end

	if not data.soldOut then
		local pidCfg = ShopModel:getPidData(cfg.buy_id)
		PriceText:SetActive(true)
		bee.setText(PriceText, ShopModel:getPriText(pidCfg))
	end
end

function P:refreshUI()
	if not self.packageList then
		return
	end
	local data = ShopModel:getShopPackageList(self.shop_type)
	self.packageList:setDatas(data)
end

