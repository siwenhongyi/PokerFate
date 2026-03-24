local P = class("Toast", UiBase)

function P:ctor()
end

function P:onAwake()
	self.inPop = true
    self.ImageBg = self:find("ImageBg")
    self.Text = self:find("Text", self.ImageBg)
    self.ImageBg.transform.localScale = bee.v3(0,0,0)
end

function P:onStart()
    if self._params and self._params.text then
        bee.setText(self.Text, self._params.text)
    end
    if not bee.isNull(self.ImageBg) then
        bee.tween(self.ImageBg)
        : to(0.08, {scale = 1})
        : by(1.5, {y = 120})
        : delay(0.5)
        : to(0.2, {alpha = 0})
        : onComplete(function()
            UiManager:hideUIByCls(self)
        end)
        : link()
    end

    if not self._params or not self._params.isSilence then
        Game:playSound("ui_toast_message")
    end
end

function P:hideUI()
    P.super.hideUI(self, nil, true)
end

function P:onDestroy()
    P.super.onDestroy(self)
end

