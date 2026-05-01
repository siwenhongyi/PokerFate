local P = class("IngameQuickBy", UiDialog)

function P:onAwake()
    self.Center = self:find("AnimRoot/Center")

    self.TitleRoot = self:find("Chips/Title", self.Center)
    self.PurchaseButton = self:find("PurchaseButton", self.Center)
    self.TextPrice = self:find("TextPrice", self.PurchaseButton)
    -- self.TextPriceOld = self:find("TextPriceOld", self.PurchaseButton)
    self.TextChip = self:find("ingame_bankrupt_chip_bg/TextChip", self.Center)
    self.TextTime = self:find("TextTime", self.Center)
    self.ingame_bankrupt_chip_01 = self:find("Box/icon_chip_2", self.Center)
    self.GreatValueFrame = self:find("Chips/ingame_bankrupt_frame_value", self.Center)
    self.GreatLayoutGroup = self:find("Tip", self.GreatValueFrame)
    self.GreatText = self:find("Text", self.GreatLayoutGroup)
    self.GreatValue = self:find("Value", self.GreatLayoutGroup)

    local lan = LanguageManager:getLanguage()
    local count = self.TitleRoot.transform.childCount
    for i = 1, count do
        self.TitleRoot.transform:GetChild(i - 1).gameObject:SetActive(false)
    end
    self:find(string.format("Title_%s", lan), self.TitleRoot):SetActive(true)

    self.TipView = nil

    bee.addClick(self:find("CloseButton", self.Center), function()
        -- Net:sendReq("pb.LeaveRoomREQ", {})
        self.TipView = UiManager:showTip({
            text = _T("LAB_SIDEGAME_PUSH_TIPS_1"),
            onSure = function()
                self:checkBankrupt()
            end,
            onCancel = function()
                self.TipView = nil
            end
        })
        self.TipView:refreshTimeText(_F("LAB_GAME_002", ShopModel:getShopTimeText2(self._dt)))
    end)
    
    bee.addClick(self.PurchaseButton, function()
        Game:playSound("ui_button_confirm")
        ShopModel:pay(self._shopData)
    end)
end

function P:onShow()
    self._dt = self._params and self._params.dt or 60
    self._data = self._params and self._params.data or tpl_table_poker[1]
    self._shopData = tpl_quick_purchase[self._data.quick_buy]

    bee.setText(self.TextChip, _N(self._shopData.props[2]))
    bee.setIcon(self.ingame_bankrupt_chip_01, self._shopData.icon, true)

    ShopModel:setTextPrice(self.TextPrice, self._shopData.buy_id)
    self.GreatValueFrame:SetActive(false)
    -- local pidData = ShopModel:getPidData(self._shopData.buy_id)
    if self._shopData.discount then
        self.GreatValueFrame:SetActive(true)
        bee.setText(self.GreatText, _T("TAB_SHOP_QUICK_PURCHASE_TIPS_1"))
        bee.setText(self.GreatValue, self._shopData.discount .. "%")
        local layoutGroup = self.GreatLayoutGroup:GetComponent("HorizontalLayoutGroup")
        layoutGroup.reverseArrangement = LanguageManager:getLanguage() == "jp"
        bee.once(0.02, function()
            layoutGroup.enabled = false
            layoutGroup.enabled = true
        end)

        -- ShopModel:setTextPriceOld(self.TextPriceOld, self._shopData.buy_id)
        -- self.TextPriceOld:SetActive(true)
        -- self.TagDiscount:SetActive(true)
    else
        -- self.TextPriceOld:SetActive(false)
        -- self.TagDiscount:SetActive(false)
        self.TextPrice.transform.localPosition = bee.v3(0, 4)
    end

    self:refreshTime()

    bee.logEvent("shop-quick_purchase", self._data.gameType, self._data.quick_buy)
end

function P:refreshTime()
    bee.setText(self.TextTime, _F("LAB_GAME_002", ShopModel:getShopTimeText2(self._dt)))
    scheduler:removeTarget(self.node)
    self:schedule(1, function()
        self._dt = self._dt - 1
        if self._dt <= 0 then
            self._dt = 0
            self:checkBankrupt()
            if self.TipView then
                self.TipView:timeOut()
            end
        end
        local str = _F("LAB_GAME_002", ShopModel:getShopTimeText2(self._dt))
        bee.setText(self.TextTime, str)

        if self.TipView then
            self.TipView:refreshTimeText(str)
        end
    end)
end

function P:evt_pay_sucess(data)
    if GameModel.data then
        local player = GameModel.data:getMyPlayerInfo()
        if player and player.chips <= 0 then
            Net:sendReq("pb.RebyREQ", {
                is_reby = true,
                chips = player.default_byin,
            })
        end
    end
    QuickByModel:clearGift()
    self:hideUI()
end

function P:checkBankrupt()
    if PlayerModel:getGold() < tpl_constdata.Bankruptcy_Protection_Balance then
        Net:sendReq("pb.BustProtectInfoREQ", {}, function(d) end)
    end
    self:hideUI()
end

return P