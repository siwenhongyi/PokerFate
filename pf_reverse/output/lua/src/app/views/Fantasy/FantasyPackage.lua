local P = class("FantasyPackage", UiDialog)

function P:onAwake()
    self._openAnim, self._closeAnim = "UI_1_FantasyPackage_into", "UI_1_FantasyPackage_back"
    self._openAnimBase, self._closeAnimBase = "UI_1_FantasyPackageBase_into", "UI_1_FantasyPackageBase_back"
    self.animator = self:find("AnimRoot")
    self.Center = self:find("AnimRoot/Center")

    self.CloseButton = self:find("CloseButton", self.Center)
    bee.addClick(self.CloseButton, function()
        self:onBtClose()
    end)

    self.packPannel = self:find("FantasyPackageBase/AnimRoot/Center/Pannel", self.Center)
    self:find("fantasy_tc_bg_zp", self.packPannel):SetActive(true)
    self:find("fantasy_tc_bg_zp_02", self.packPannel):SetActive(false)
end

function P:onBtClose()
    AnimationMgr:playAnimator(self.animator, self._closeAnim)
    local centerObj = self:find("FantasyPackageBase", self.Center)
    AnimationMgr:playAnim(self:find("AnimRoot", centerObj), self._closeAnimBase, function()
        self._closeAnim = ""
        self:hideUI()
    end)
end

return P