local P = class("HotSpringHallRule", UiDialog)

function P:onAwake()
    self._isMute = true
    self.Center = self:find("AnimRoot/Center")

    bee.addClick(self:find("CloseButton", self.Center), function()
        Game:playSound("ui_button_confirm")
        self:hideUI()
    end)
end

function P:onShow()
    P.super.onShow(self)
    bee.logEvent("onsen-rules")
end

