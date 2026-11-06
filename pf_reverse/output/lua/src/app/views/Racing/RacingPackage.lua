local P = class("RacingPackage", UiDialog)

function P:onAwake()
    -- self._openAnim, self._closeAnim = "UI_1_" .. self.__cname .. "_into", "UI_1_" .. self.__cname .. "_back"
    self._openAnim, self._closeAnim = "UI_1_RacingPackage_into", "UI_1_RacingPackage_back"
    self._openAnimBase, self._closeAnimBase = "UI_1_RacingPackageBase_into", "UI_1_RacingPackageBase_back"
    self.animator = self:find("AnimRoot")
    self.Center = self:find("AnimRoot/Center")

    self.CloseButton = self:find("CloseButton", self.Center)
    bee.addClick(self.CloseButton, function()
        self:onBtClose()
    end)
end

function P:onBtClose()
    AnimationMgr:playAnimator(self.animator, self._closeAnim)
    local centerObj = self:find("RacingPackageBase", self.Center)
    AnimationMgr:playAnim(self:find("AnimRoot", centerObj), self._closeAnimBase, function()
        self._closeAnim = ""
        self:hideUI()
    end)
end

return P