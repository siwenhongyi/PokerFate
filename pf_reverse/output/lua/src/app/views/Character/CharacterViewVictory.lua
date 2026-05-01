local P = class("CharacterViewVictory", UiBase)

function P:onAwake()
    P.super.onAwake(self)

    local AnimRoot = self:find("AnimRoot")
    local LeftTop = self:find("LeftTop", AnimRoot)

    self.CharacterImage = self:find("Center/CharacterImage", AnimRoot)

    bee.addClick(self:find("BackButton", LeftTop), function()
        self:hideUI()
    end)
    bee.addClick(self:find("InfoButton", LeftTop), function()
        UiManager:showUI("CommonRules", {text = _T("LAB_BOND_RULES_1")})
    end)
    bee.addClick(self:find("RightBottom/ReplayButton", AnimRoot), function()
        bee.invoke(self.CharacterImage, "playAnim", "idle")
    end)
end

function P:onShow()
    self._role = self._params.data or self._params.role
    self._skin = self._params.skin
    if self._skin then
        bee.invoke(self.CharacterImage, "setSkin", self._skin, true, true)
    else
        bee.invoke(self.CharacterImage, "setRole", self._role, true, true)
    end
end

return P