local P = class("SpringFestivalShopItem", Object)

function P:onAwake()
    self.AniRoot = self:find("Ani_root")
    self.Name = self:find("Name", self.AniRoot)
    self.FrameButton = self:find("spring_shop_bg_backpack", self.AniRoot)
    self.BuyButton = self:find("BuyButton", self.AniRoot)
    self.PriceText = self:find("BuyButton/Value", self.AniRoot)
    self.LimitText = self:find("LimitText", self.AniRoot)
    self.Icon = self:find("Icon", self.AniRoot)
    self.SoldOut = self:find("SoldOut", self.AniRoot)
    self.Mask = self:find("spring_shop_img_mask", self.AniRoot)
end

function P:refreshItem(cfg, mask, index)
    self:once(0.1 * (index - 1), function()
        self.AniRoot:SetActive(true)
    end)
    self.AniRoot:SetActive(false)

    bee.setText(self.Name, _T(cfg.name))
    bee.setIcon(self.Icon, cfg.icon)
    local limit = string.format("%d/%d", mask and cfg.limit_count or 0, cfg.limit_count)
    bee.setText(self.LimitText, _T("LAB_SHOP_COMMON_14") .. ": " .. limit)
    local pidCfg = ShopModel:getPidData(cfg.buy_id)
    bee.setText(self.PriceText, ShopModel:getPriText(pidCfg))

    self.BuyButton:SetActive(not mask)
    self.SoldOut:SetActive(mask)
    self.Mask:SetActive(mask)

    local action = function()
        Game:playSound("ui_button_confirm")
        local data = {cfg = cfg, soldOut = false, buyCount = 0}
        UiManager:showUI("ShopPurchasePackage", {data = data})
    end

    if not mask then
        bee.removeAllClick(self.BuyButton)
        bee.addClick(self.BuyButton, action)
        bee.addClick(self.FrameButton, action)
    end
end

