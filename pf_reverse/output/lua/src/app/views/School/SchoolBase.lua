local P = class("SchoolBase", UiFullView)

function P:onAwake()
    self._isMute = true

    self.AnimRoot = self:find("AnimRoot")
    self.Center = self:find("Center", self.AnimRoot)
    self.Right = self:find("Right", self.AnimRoot)
    self.RightTop = self:find("RightTop", self.AnimRoot)
    self.LeftTop = self:find("LeftTop", self.AnimRoot)
    self.Left = self:find("Left", self.AnimRoot)

    self.BackButton = self:find("BackButton", self.LeftTop)
    self.TipsButton = self:find("TipsButton", self.LeftTop)
    self.PropButton = self:find("Currency/school_main_icon_currency", self.RightTop)
    self.TextCount = self:find("Currency/Value", self.RightTop)
    self.PlusFrameButton = self:find("Currency/school_main_currency_bg", self.RightTop)
    self.PlusButton = self:find("Currency/PlusButton", self.RightTop)

    self.RoleButton = self:find("RoleButton", self.AnimRoot)
    self.Tip = self:find("Tip", self.Left)
    self.TextTip = self:find("Tip/Text", self.Left)
    self.CacheTips = {}
    self.LastStr = ""

    self.CharacterImage = self:find("CharacterImage", self.AnimRoot)

    bee.addClick(self.BackButton, function()
       Game:playSound("ui_button_confirm")
       self:hideUI()
    end)

    bee.addClick(self.TipsButton, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("SchoolRules")
    end)

    bee.addClick(self.PlusFrameButton, function()
        Game:playSound("ui_button_confirm")
        ItemModel:jumpView(5001)
    end)
    bee.addClick(self.PlusButton, function()
        Game:playSound("ui_button_confirm")
        ItemModel:jumpView(5001)
    end)

    bee.addClick(self.RoleButton, function()
        if bee.checkCd("School_RoleButton", 1) then
            self:showRoleTip()
        end
    end)

    self:clickActiveItem(self.PropButton)
end

function P:onShow()
    self:evt_refreshTopInfo()

    self:showRoleTip()
end

--点击活动道具
function P:clickActiveItem(obj)
	bee.addClick(obj, function()
		Game:playSound("ui_button_confirm")
		UiManager:showUI("CommonItemTip", {data = ItemModel:getItem(ThemeModel:getItemId(), true), target = obj})
    end, true)
end

--点击获得道具跳转
function P:clickToGetProp(obj)
    bee.addClick(obj, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("SchoolTask")
    end, true)
end

function P:showRoleTip()
    if not self.Tip then
        return
    end
    if not self._tips then
        self.Tip:SetActive(false)
        return
    end
    if #self.CacheTips == 0 then
        for _,v in pairs(self._tips) do
            if self.LastStr ~= v then
                table.insert(self.CacheTips, v)
            end
        end
    end

    local index = math.random(#self.CacheTips)
    self.LastStr = self.CacheTips[index]
    table.remove(self.CacheTips, index)
    bee.setText(self.TextTip, _T(self.LastStr))
    self.Tip:SetActive(true)
    bee.Tween.killByTarget(self.Tip)

    bee.setAlpha(self.Tip, 0)
    bee.tween(self.Tip)
    : to(0.5, {alpha = 1})
    : delay(3)
    : to(0.5, {alpha = 0})
    : onComplete(function()
        self.Tip:SetActive(false)
    end)
    : link()
    : setTarget()
end


function P:evt_refreshTopInfo()
    bee.setTextGold(self.TextCount, _N(ItemModel:getItemNumById(ThemeModel:getItemId())))
end

function P:hideTopUI()
    self.LeftTop:SetActive(false)
    self.RightTop:SetActive(false)
end

return P