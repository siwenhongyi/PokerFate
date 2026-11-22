local P = class("ShopLimitedPackage", UiFullView)

function P:onAwake()
	local Panel = self:find("AnimRoot/Center/Panel")

    self.PurchaseButton = self:find("Price", Panel)
    self.PriceValue = self:find("Price/Value", Panel)
    self.ChipIcon = self:find("Item1/icon_chip_2", Panel)
    self.ChipCount = self:find("Label2/Value", Panel)
    self.PassText = self:find("Label1/Text", Panel)
    self.TextTime = self:find("Label1/Time", Panel)

    self.giftCfg = nil
    bee.addClick(self.PurchaseButton, function()
        Game:playSound("ui_button_confirm")
        ShopModel:pay(self.giftCfg)
    end)

	self.CloseButton = self:find("CloseButton", Panel)
	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)
end

function P:onShow()
    self.giftCfg = tpl_quick_purchase[QuickByModel.vip_gift_id]
    if self.giftCfg == nil then
        self:hideUI()
        return
    end

    -- if self._params and self._params.push then
    --     bee.logEvent("shop-extra_purchase", self._params.gameType or 0, QuickByModel.limit_gift_id)
    -- end

    -- ShopModel:setTextPrice(self.PriceValue, self.giftCfg.buy_id)
    -- bee.setText(self.ChipCount, _N(self.giftCfg.props[2]))
    -- bee.setIcon(self.ChipIcon, self.giftCfg.image, true)
    -- local fixData = self.sizeDic[QuickByModel.limit_gift_id]
    -- if fixData then
    --     self.ChipIcon.transform.localScale = bee.v3one * fixData.size
    --     local pos = self.ChipIcon.transform.localPosition
    --     pos = bee.v3(pos.x, pos.y + fixData.posy, pos.z)
    --     self.ChipIcon.transform.localPosition = pos
    -- end

    -- bee.setText(self.PassText, _F("TAB_EXTRA_PURCHASE_103", self.giftCfg.discount))

    self._dt = QuickByModel.vip_endTime - bee.getServerTime()
    self:refreshTime()
end

function P:refreshTime()
    bee.setText(self.TextTime, _T(ShopModel:getShopTimeText2(self._dt)))
    scheduler:removeTarget(self.node)
    self:schedule(1, function()
        self._dt = self._dt - 1
        if self._dt <= 0 then
            self._dt = 0
            self:hideUI()
        end
        local str = _T(ShopModel:getShopTimeText2(self._dt))
        bee.setText(self.TextTime, str)
    end)
end

function P:evt_pay_sucess(data)
    self:hideUI()
end

return P