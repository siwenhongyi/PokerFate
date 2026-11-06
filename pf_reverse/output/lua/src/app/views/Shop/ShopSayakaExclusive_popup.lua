local P = class("ShopGiftsPushView", UiFullView)

function P:onAwake()
	local AnimRoot = self:find("AnimRoot")

	self.CloseButton = self:find("CloseButton", AnimRoot)
	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)
end

function P:onStart()
end

return P