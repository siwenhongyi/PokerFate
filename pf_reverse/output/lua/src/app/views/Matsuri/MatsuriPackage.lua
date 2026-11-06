local P = class("MatsuriPackage", UiDialog)

function P:onAwake()
    self._openAnim, self._closeAnim = "UI_1_" .. self.__cname .. "_into", "UI_1_" .. self.__cname .. "_back"
	self.Center = self:find("AnimRoot/Center")

    self.CloseButton = self:find("CloseButton", self.Center)
    bee.addClick(self.CloseButton, function()
        self:onBtClose()
    end)
end

function P:onBtClose()
    AnimationMgr:playAnimator(self.animator, self._closeAnim)
    local centerObj = self:find("MatsuriPackageBase", self.Center)
    AnimationMgr:playAnim(self:find("AnimRoot", centerObj), self._closeAnim, function()
        self._closeAnim = ""
        self:hideUI()
    end)
end

return P