local P = class("RecruitmentBundles", UiDialog)

function P:onAwake()
	local Center = self:find("AnimRoot/Center")

	self.PackageScrollList = self:find("PackageScrollList", Center)
	self.Item01 = self:find("Item01", self.PackageScrollList)
	self.Item02 = self:find("Item02", self.PackageScrollList)
	self.Item03 = self:find("Item03", self.PackageScrollList)
	self.Item01:SetActive(false)
	self.Item02:SetActive(false)
	self.Item03:SetActive(false)

	self.CloseButton = self:find("CloseButton", Center)
	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)
end

function P:onStart()
	self:initPackageList()
	self:setPackageList()
end

function P:evt_updateShopLimit()
	self:setPackageList()
end

function P:initPackageList()
	self.packageList = UiListEx:create(self.PackageScrollList)
	self.packageList:setCreateFunc(function(data)
		if data.__kind == 1 then
			return CU.GameObject.Instantiate(self.Item01)
		elseif data.__kind == 2 then
			return CU.GameObject.Instantiate(self.Item02)
		else
			return CU.GameObject.Instantiate(self.Item03)
		end
	end)
	self.packageList:setRefreshFunc(function(data, item, isInit, index)
		self:setItemPackage(item, data, isInit, index)
	end)
	self.packageList:setWidth(312)
end

function P:setPackageList()
	local data = ShopModel:getShopPackageList(SHOP_TYPE.shop_gifts)
	for k,v in pairs(data) do
		if v.soldOut then
			v.__kind = 3
		elseif v.cfg.goods_bg == 1 then
			v.__kind = 1
		else
			v.__kind = 2
		end
	end
	self.packageList:setDatas(data)
end

function P:setItemPackage(item, data, isInit, index)
	local Ani_root = self:find("Ani_root", item)
	local PriceText = self:find("PriceText", Ani_root)

	if isInit then
        self:once(0.1 * (index - 1), function()
            Ani_root:SetActive(true)
            self:playAnimator("UI_1_AchievementMain_item", Ani_root)
        end)
        Ani_root:SetActive(false)
    else
        Ani_root:SetActive(true)
        self:playAnimator("UI_1_AchievementMain_item_idle", Ani_root)
    end
	
	self:setItem(item, data)

	bee.removeAllClick(item)
	bee.addClick2(item, function()
		if data.soldOut then
			UiManager:showToast(_T("LAB_SHOP_COMMON_9"))
			return
		end
		Game:playSound("ui_button_confirm")
		
		local cfg = data.cfg
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

	local cfg = data.cfg
	bee.setText(NameText, _T(cfg.name))
	bee.setIconInAtlas(PackageIcon, cfg.icon)

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

	local propCfg = tpl_props[cfg.props[1]]
	if cfg.props[2] > 1 then
		bee.setText(ItemText, _T(propCfg.name) .. " x" .. cfg.props[2])
	else
		bee.setText(ItemText, _T(propCfg.name))
	end

	if not data.soldOut then
		local pidCfg = ShopModel:getPidData(cfg.buy_id)
		bee.setText(PriceText, ShopModel:getPriText(pidCfg))
	end
end

return P