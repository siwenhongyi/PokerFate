local P = class("ShopFashionCredit", UiDialog)

function P:onAwake()
	local Center = self:find("AnimRoot/Center")

	self.TopUpScrollList = self:find("Main/TopUpScrollList", Center)
	self.TopUpItem = self:find("TopUpItem", self.TopUpScrollList)
	self.TopUpItem:SetActive(false)

	self.CloseButton = self:find("CloseButton", Center)
	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)
end

function P:onStart()
	self:initTopUpList()
	self:setTopUpList()
end

function P:initTopUpList()
	self.topUpList = UiListEx:create(self.TopUpScrollList)
	self.topUpList:setCreateFunc(function(data)
		return CU.GameObject.Instantiate(self.TopUpItem)
	end)
	self.topUpList:setRefreshFunc(function(data, item, isInit, index)
		self:setTopUpItem(item, data, isInit, index)
	end)
	self.topUpList:setWidth(355)
end

function P:setTopUpList()
	local datas = ShopModel:getShopTopUpList(SHOP_TYPE.shop_recharge2)
	self.topUpList:setDatas(datas)
end

function P:setTopUpItem(item, data, isInit, index)
	local Ani_root = self:find("Ani_root", item)
	local ItemBg = self:find("ItemBg", Ani_root)
	local ItemIcon = self:find("ItemIcon", Ani_root)
	local CountText = self:find("CountBg/CountText", Ani_root)
	local PriceText = self:find("PriceText", Ani_root)

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

	if cfg.buy_id == 0 then
		PriceText:SetActive(true)
		bee.setText(PriceText, _T("LAB_SHOP_COMMON_21"))
	else
		local pidCfg = ShopModel:getPidData(cfg.buy_id)
		PriceText:SetActive(true)
		bee.setText(PriceText, ShopModel:getPriText(pidCfg))
	end

	bee.removeAllClick(item)
	bee.addClick2(item, function()
		if data.soldOut then
			UiManager:showToast(_T("LAB_SHOP_COMMON_9"))
			return
		end
		
		Game:playSound("ui_button_confirm")
		ShopModel:pay(cfg)
	end)
end

return P