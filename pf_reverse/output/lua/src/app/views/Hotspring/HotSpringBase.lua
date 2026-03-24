local P = class("HotSpringShop", UiFullView)

function P:onAwake()
    self._isMute = true
    
    self.AnimRoot = self:find("AnimRoot")
    self.RightTop = self:find("RightTop", self.AnimRoot)
    self.Right = self:find("Right", self.AnimRoot)
    self.LeftTop = self:find("LeftTop", self.AnimRoot)
    self.RightBottom = self:find("RightBottom", self.AnimRoot)
    self.LeftBottom = self:find("LeftBottom", self.AnimRoot)
    self.TextCount = self:find("Ticket2/TextCount", self.RightTop)
    self.CharacterImage = self:find("CharacterImage", self.AnimRoot)
    self.frame_dialog_box = self:find("frame_dialog_box", self.AnimRoot)
    self.TextTip = self:find("frame_dialog_box/TextTip", self.AnimRoot)

    bee.addClick(self:find("btn_back", self.LeftTop), function()
        Game:playSound("ui_button_confirm")
        self:hideUI()
    end)
    bee.addClick(self:find("hotspring_btn_tips", self.LeftTop), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("HotSpringHallRule")
    end)
    bee.addClick(self:find("Ticket2", self.RightTop), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("HotSpringHallBlind")
    end)
    bee.addClick(self:find("Ticket2/Icon", self.RightTop), function()
        UiManager:showUI("CommonItemTip", {data = ItemModel:getItem(ThemeModel:getItemId(), true), target = self:find("Ticket2/Icon", self.RightTop)})
    end)

    self._tips = {"LAB_STORY_DIALOGUE_S1_1003_01", "LAB_STORY_DIALOGUE_S1_1003_02", "LAB_STORY_DIALOGUE_S1_1003_03"}
    bee.addClick2(self:find("RoleButton", self.AnimRoot), function()
        if bee.checkCd("HotSpringShop_RoleButton", 1) then
            self:showRoleTip()
        end
    end)
end

function P:onShow()
    self:evt_refreshTopInfo()
    self:showRoleTip()
end

function P:showRoleTip()
    if not self._tips then
        self.frame_dialog_box:SetActive(false)
        return
    end
    bee.setText(self.TextTip, _T(self._tips[math.random(#self._tips)]))
    self.frame_dialog_box:SetActive(true)
    bee.Tween.killByTarget(self.frame_dialog_box)

    bee.setAlpha(self.frame_dialog_box, 0)
    bee.tween(self.frame_dialog_box)
    : to(0.5, {alpha = 1})
    : delay(3)
    : to(0.5, {alpha = 0})
    : onComplete(function()
        self.frame_dialog_box:SetActive(false)
    end)
    : link()
    : setTarget()
end

function P:evt_refreshTopInfo()
    bee.setTextGold(self.TextCount, _N(ItemModel:getItemNumById(ThemeModel:getItemId())))
end

