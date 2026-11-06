local P = class("ShopBestsellerColorCrystal", UiBase)

function P:onAwake()
	local Pannel = self:find("Pannel")
	self.TopUpItem = self:find("TopUpItem", Pannel)
	self.PackList = self:find("PackList", Pannel)
	self.TopUpItem:SetActive(false)
end

function P:onStart()
	self:initTopUpList()
	self:refreshUI()
end

function P:initTopUpList()
	self.topUpList = UiListEx:create(self.PackList)
	self.topUpList:setCreateFunc(function(data)
		return CU.GameObject.Instantiate(self.TopUpItem)
	end)
	self.topUpList:setRefreshFunc(function(data, item, isInit, index)
		self:setTopUpItem(item, data, isInit, index)
	end)
	self.topUpList:setWidth(360)
end

function P:refreshUI()
	if not self.topUpList then
		self:initTopUpList()
	end

	local datas = ShopModel:getShopTopUpList(SHOP_TYPE.shop_recharge)

	local list1 = {}
	local list2 = {}
	for i,v in ipairs(datas) do
		local isCanDouble = ShopModel:getIsCanDoubleReward(v.cfg.shop_type, v.cfg.id)
		if isCanDouble then
			table.insert(list1, v)
		else
			table.insert(list2, v)
		end
	end
	for i,v in ipairs(list2) do
		table.insert(list1, v)
	end
	self.topUpList:setDatas(list1)
end

function P:setTopUpItem(item, data, isInit, index)
	local Ani_root = self:find("Ani_root", item)
	local ItemIcon = self:find("ItemIcon", Ani_root)
	local CountText = self:find("CountBg/CountText", Ani_root)
	local PriceText = self:find("PriceText", Ani_root)
	local RedPoint = self:find("RedPoint", Ani_root)
	local TagDouble = self:find("TagDouble", Ani_root)
	local DoubleText = self:find("DoubleText", TagDouble)
	local SoldOut = self:find("SoldOut", Ani_root)
	local RedPoint = self:find("RedPoint", Ani_root)

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

	local cfg = data.cfg
	bee.setText(CountText, "x" .. _N(cfg.props[2]))
	bee.setIconInAtlas(ItemIcon, cfg.icon, true)

	RedManager:unbind(RedPoint)
	if cfg.buy_id == 0 then
		RedManager:bind(RedPoint, RedTag.DailyFree)
	else
		RedPoint:SetActive(false)
	end

	local isCanDouble = ShopModel:getIsCanDoubleReward(cfg.shop_type, cfg.id)
	if isCanDouble then
		TagDouble:SetActive(true)
		bee.setText(DoubleText, "+" .. cfg.props[2])
		SoldOut:SetActive(false)
	else
		TagDouble:SetActive(false)
		SoldOut:SetActive(true)
	end

	local pidCfg = ShopModel:getPidData(cfg.buy_id)
	PriceText:SetActive(true)
	bee.setText(PriceText, ShopModel:getPriText(pidCfg))

	bee.removeAllClick(item)
	bee.addClick2(item, function()
		if not isCanDouble then
			UiManager:showToast(_T("TAB_SHOP_HOT_8"))
			return
		end

		bee.logEvent("shop-goods-tap", cfg.shop_type, cfg.id)
		
		if cfg.buy_id == 0 then
			-- 领取免费奖励
			ShopModel:requestReward(cfg.shop_type, cfg.id)
			TaskModel:reportTask(TaskType.ClaimDailyFree)
		else
			Game:playSound("ui_button_confirm")
			ShopModel:pay(cfg)
		end
	end)
end

return P