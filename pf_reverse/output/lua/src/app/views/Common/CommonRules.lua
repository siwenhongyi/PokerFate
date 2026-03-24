local P = class("CommonRules", UiDialog)

function P:onAwake()
    local Center = self:find("AnimRoot/Center")
    self.TextTitle = self:find("TextTitle", Center)
    self.TextTip = self:find("TextList/Viewport/Content/TextTip", Center)

	bee.addClick(self:find("CloseButton", Center), function()
		self:hideUI()
	end)
end

function P:onShow()
    if self._params then
        if self._params.title then
            bee.setText(self.TextTitle, self._params.title)
        end
        bee.setText(self.TextTip, self._params.text)
    end
end

