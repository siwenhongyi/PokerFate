local P = class("SpiritCatStyleLevelUp", UiBase)

function P:onAwake()
	self.Number = self:find("AnimRoot/Top/Icon/Number")
	self.Num1 = self:find("Num1", self.Number)
	self.Num2 = self:find("Num2", self.Number)
	self.Num3 = self:find("Num3", self.Number)
end

function P:onStart()
	self:setLevelText(BattlePassModel:getCurPassLevel())
	self:once(2, function()
		self:hideUI()
	end)
end

function P:setLevelText(curLevel)
	local h = math.floor(curLevel / 100)
	local t = math.floor((curLevel - h * 100) / 10)
	local u = curLevel - h * 100 - t * 10
	if h > 0 then
		self.Num1:SetActive(true)
		bee.setIcon(self.Num1, "spiritcat_number_" .. h, "Spiritcat")
	else
		self.Num1:SetActive(false)
	end
	if h > 0 or t > 0 then
		self.Num2:SetActive(true)
		bee.setIcon(self.Num2, "spiritcat_number_" .. t, "Spiritcat")
	else
		self.Num2:SetActive(false)
	end
	bee.setIcon(self.Num3, "spiritcat_number_" .. u, "Spiritcat")

	bee.setText(self.RewardText, _F("TAB_BATTLE_PASS_21", curLevel))
end

return P