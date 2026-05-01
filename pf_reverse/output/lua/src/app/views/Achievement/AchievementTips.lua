local P = class("AchievementTips", UiBase)

function P:onAwake()
    P.super.onAwake(self)
    self.inPop = true
    self._openAnim, self._closeAnim = "UI_1_" .. self.__cname .. "_into", "UI_1_" .. self.__cname .. "_back"

    self.Ani = self:find("AnimRoot")
    self.Top = self:find("AnimRoot/Top")
    self.Title = self:find("Title", self.Top)
    self.icon = self:find("icon", self.Top)
end

function P:onShow()
    self.clearIds = self._params.clearIds
    table.sort( self.clearIds, function (a, b)
        return a < b
    end)


    local gachaShowUI = UiManager:getUI("GachaResultShow")
    local gachaVideoUI = UiManager:getUI("GachaWheelMask")
    if gachaShowUI or gachaVideoUI then
        self.Ani:SetActive(false)
    else
        self:showTip()
    end
end

function P:showTip()
    local id = self.clearIds[1]
    local cfg = tpl_achievement_task[id]
    bee.setText(self.Title, _T(cfg.name))
    bee.setIcon(self.icon, string.format("achievement_level_%s", cfg.ach_level), "Achievement", true)

    table.remove(self.clearIds, 1)
    self:playAnimator(self._openAnim)
    self:once(2, function ()
        if table.nums(self.clearIds) == 0 then
            self:hideUI()
        else
            self:playAnimator(self._closeAnim)
            self:once(0.5, function ()
                self:showTip()
            end)
        end
    end)
end

function P:evt_gachaOver()
    self.Ani:SetActive(true)
    self:showTip()
end

return P