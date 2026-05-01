local P = class("ShopMonthlyCardRules", UiDialog)

function P:onAwake()
	bee.addClick(self:find("AnimRoot/Center/CloseButton"), function()
		self:hideUI()
	end)
end

return P