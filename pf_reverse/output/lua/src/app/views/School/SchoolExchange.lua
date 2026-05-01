local P = class("SchoolExchange", require("app.views.Shop.ShopExchangeBatch"))

function P:onAwake()
    P.super.onAwake(self)

    self.Batch = self:find("Batch", self.Center)
    self.Single = self:find("Single", self.Center)

    self.TextPrice = self:find("TextPrice", self.Single)

    self.PurchaseGrayButton = self:find("PurchaseGrayButton", self.Single)
    self.PurchaseButton = self:find("PurchaseButton", self.Single)

	bee.addClick(self.PurchaseButton, function()
		-- bee.logEvent("shop-goods-tap", self._params.data.cfg.shop_type, self._params.data.cfg.id)
		self:onClickExchange()
	end)
	bee.addClick(self.PurchaseGrayButton, function()
		self:onClickExchange()
	end)
end

function P:onShow()
    P.super.onShow(self)
    if self._params.isSingle then
        self.Batch:SetActive(false)
        self.Single:SetActive(true)

        self:refreshContSingle()
    else
        self.Batch:SetActive(true)
        self.Single:SetActive(false)
    end
end

function P:refreshContSingle()
	local data = self._params.data
	local cfg = self._params.data.cfg
    
	local consumeId = cfg.exchange_cost and cfg.exchange_cost[1] or cfg.pri[1]
	local consumeCount = cfg.exchange_cost and cfg.exchange_cost[2] or cfg.pri[2]
	local ownCount = ItemModel:getItemNumById(consumeId)

	if ownCount >= consumeCount then
		self.PurchaseButton:SetActive(true)
		self.PurchaseGrayButton:SetActive(false)

		-- self.RedPriText:SetActive(false)
		-- self.Line:SetActive(false)
	else
		self.PurchaseButton:SetActive(false)
		self.PurchaseGrayButton:SetActive(true)

		-- self.RedPriText:SetActive(true)
		-- self.Line:SetActive(true)
		-- bee.setText(self.RedPriText, ownCount)
	end

	bee.setIconInAtlas(self.PriIcon, tpl_props[consumeId].icon)
	bee.setText(self.TextPrice, consumeCount)
end

function P:evt_ItemChangeRSP(msg)
    self:onShow()
end


return P