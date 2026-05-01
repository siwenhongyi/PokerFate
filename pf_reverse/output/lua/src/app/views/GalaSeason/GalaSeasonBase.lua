local P = class("GalaSeasonMain", UiFullView)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Center = self:find("Center", self.AnimRoot)
    self.LeftTop = self:find("LeftTop", self.AnimRoot)
    self.LeftBottom = self:find("LeftBottom", self.AnimRoot)
    self.Right = self:find("Right", self.AnimRoot)
    self.RightTop = self:find("RightTop", self.AnimRoot)
    self.RightBottom = self:find("RightBottom", self.AnimRoot)
    self.CharacterImage = self:find("CharacterImage", self.AnimRoot)

    self.TextGold = self:find("Currency/TextGold", self.RightTop)
    self.TIP = self:find("TIP", self.AnimRoot)
    self.TextTip = self:find("TIP/TextTip", self.AnimRoot)


    bee.addClick2(self:find("Currency/gala_main_icon_currency", self.RightTop), function()
        UiManager:showUI("CommonItemTip", {data = ItemModel:getItem(ThemeModel:getItemId(), true), target = self:find("Currency/gala_main_icon_currency", self.RightTop)})
    end)

    bee.addClick(self:find("Currency", self.RightTop), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("TournamentLobby")
    end)

    bee.addClick(self:find("BackButton", self.LeftTop), function()
        self:hideUI()
    end)
    bee.addClick(self:find("TipsButton", self.LeftTop), function()
        UiManager:showUI("GalaSeasonRules")
    end)
    
    bee.addClick2(self:find("RoleButton", self.AnimRoot), function()
        if bee.checkCd("GalaSeason_RoleButton", 1) then
            self:showRoleTip()
        end
    end)
end

function P:onShow()
    self:evt_refreshTopInfo()

    self:showRoleTip()
end

function P:showRoleTip()
    if not self.TIP then
        return
    end
    if not self._tips then
        self.TIP:SetActive(false)
        return
    end
    bee.setText(self.TextTip, _T(self._tips[math.random(#self._tips)]))
    self.TIP:SetActive(true)
    bee.Tween.killByTarget(self.TIP)

    bee.setAlpha(self.TIP, 0)
    bee.tween(self.TIP)
    : to(0.5, {alpha = 1})
    : delay(3)
    : to(0.5, {alpha = 0})
    : onComplete(function()
        self.TIP:SetActive(false)
    end)
    : link()
    : setTarget()
end

function P:evt_refreshTopInfo()
    bee.setTextGold(self.TextGold, _N(ItemModel:getItemNumById(ThemeModel:getItemId())))
end

return P