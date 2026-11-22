local P = class("HalloweenPackage", UiDialog)

function P:onAwake()
    -- self._openAnim, self._closeAnim = "UI_1_" .. self.__cname .. "_into", "UI_1_" .. self.__cname .. "_back"
	self._openAnim, self._closeAnim = "UI_1_MatsuriPackage_into", "UI_1_MatsuriPackage_back"
    self.animator = self:find("AnimRoot")
    self.Center = self:find("AnimRoot/Center")

    self.baseObj = self:find("HalloweenPackageBase", self.Center)
    self.CloseButton = self:find("AnimRoot/Center/Pannel/halloween_package_close", self.baseObj)
    self.CloseButton:SetActive(true)
    bee.addClick(self.CloseButton, function()
        self:onBtClose()
    end)
end

function P:onBtClose()
    AnimationMgr:playAnimator(self.animator, self._closeAnim)
    local closeAnim = "UI_1_HalloweenPackageBase_back"
    AnimationMgr:playAnim(self:find("AnimRoot", self.baseObj), closeAnim, function()
        self._closeAnim = ""
        self:hideUI()
    end)
end

return P