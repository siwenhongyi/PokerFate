local P = class("ShopMonthlyCardEffect", UiBase)

function P:onAwake()
end

function P:onStart()
	self:once(1.5, function()
		if self._params.closeCb then
			self._params.closeCb()
		end
		self:hideUI()
	end)
end

return P