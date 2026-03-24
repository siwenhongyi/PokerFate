local P = class("SevenDayTaskTips", UiDialog)

function P:onAwake()
	local AnimRoot = self:find("AnimRoot")
	self.CloseButton = self:find("Center/CloseButton", AnimRoot)

	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)
end

