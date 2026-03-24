local P = class("ShopTopUp", UiBase)

local ItemBgList = {
	[7] = "Shop[shop_currency_crystal_bg_01]",
	[8] = "Shop[shop_currency_credits_bg_01]",
	[9] = "Shop[shop_currency_chip_bg_01]",
}

function P:onAwake()
	self.TopUpItem = self:find("TopUpItem")
	self.TopUpScrollList = self:find("TopUpScrollList")
	self.TopUpItem:SetActive(false)
end

local ROW_COUNT = 4
function P:onStart()
	self.shop_type = self._params.shop_type

	-- 任务-查看商城福利
	if self.shop_type == SHOP_TYPE.shop_recharge3 then
		TaskModel:reportTask(TaskType.CheckView, TaskTargetId.ShopChip)
	end

	local rowPos = {}
	for i = 1, ROW_COUNT do
		if i == 1 then
			table.insert(rowPos, 190)
		else
			table.insert(rowPos, 380 * i - 190)
		end
	end

	self.topUpList = UiListEx:create(self.TopUpScrollList)
	self.topUpList:setCreateFunc(function()
		return CU.GameObject.Instantiate(self.TopUpItem)
	end)
	self.topUpList:setRefreshFunc(function(data, item, isInit, index)
		self:setTopUpItem(item, data, isInit, index)
	end)
	self.topUpList:setRowCount(ROW_COUNT)
	self.topUpList:setRowPostions(rowPos)
	self.topUpList:setWidth(510)

	local datas = ShopModel:getShopTopUpList(self.shop_type)
	self.topUpList:setDatas(datas)
end

function P:setTopUpItem(item, data, isInit, index)
	local Ani_root = self:find("Ani_root", item)
	local ItemBg = self:find("ItemBg", Ani_root)
	local ItemIcon = self:find("ItemIcon", Ani_root)
	local CountText = self:find("CountBg/CountText", Ani_root)
	local PriceText = self:find("PriceText", Ani_root)
	local RedPoint = self:find("RedPoint", Ani_root)
	local TagDouble = self:find("TagDouble", Ani_root)
	local DoubleText = self:find("DoubleText", TagDouble)
	local TagExtra = self:find("TagExtra", Ani_root)
	local ExtraText = self:find("ExtraText", TagExtra)
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

	bee.setIconInAtlas(ItemBg, ItemBgList[self.shop_type])

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
	else
		TagDouble:SetActive(false)
	end
	if cfg.extra then
		TagExtra:SetActive(true)
		bee.setText(ExtraText, _F("LAB_SHOP_RECHARGE_2", cfg.extra))
	else
		TagExtra:SetActive(false)
	end

	if data.soldOut then
		SoldOut:SetActive(true)
		PriceText:SetActive(false)
	else
		SoldOut:SetActive(false)
		if cfg.buy_id == 0 then
			PriceText:SetActive(true)
			bee.setText(PriceText, _T("LAB_SHOP_COMMON_21"))
		else
			local pidCfg = ShopModel:getPidData(cfg.buy_id)
			PriceText:SetActive(true)
			bee.setText(PriceText, ShopModel:getPriText(pidCfg))
		end
	end

	bee.removeAllClick(item)
	bee.addClick2(item, function()
		if data.soldOut then
			UiManager:showToast(_T("LAB_SHOP_COMMON_9"))
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

function P:refreshUI()
	local datas = ShopModel:getShopTopUpList(self.shop_type)
	self.topUpList:setDatas(datas)
end

