local P = class("SayakaPackage", UiDialog)

function P:onAwake()
    self.Center = self:find("AnimRoot/Center")

    self.CloseButton = self:find("CloseButton", self.Center)
    bee.addClick(self.CloseButton, function()
        self:onBtClose()
    end)
end

function P:onBtClose()
    AnimationMgr:playAnimator(self.animator, self._closeAnim)
    self._closeAnim = ""
    local centerObj = self:find("SayakaPackageBase", self.Center)
    AnimationMgr:playAnim(self:find("AnimRoot", centerObj), "UI_1_SayakaPackage_back", function()
        self:hideUI()
    end)
end

return P