local P = class("GamePlayRoom", UiFullView)

function P:onAwake()
	local AnimRoot = self:find("AnimRoot")

	local Center = self:find("Center", AnimRoot)
	self.GameList = self:find("GameList", Center)
	self.ItemOmaha = self:find("ItemOmaha", self.GameList)
	self.ItemAllIn = self:find("ItemAllIn", self.GameList)

	local RightTop = self:find("RightTop", AnimRoot)
	self.GoldItem = self:find("GoldItem", RightTop)

	local LeftTop = self:find("LeftTop", AnimRoot)
	self.BackButton = self:find("BackButton", LeftTop)

	bee.addClick(self.BackButton, function()
		self:hideUI()
	end)

	bee.addClick(self.ItemOmaha, function()
		Game:playSound("ui_button_confirm")
		bee.logEvent("lobby-format-game", 1)
        UiManager:showUI("OmahaBlinds", {gameType = GAME_GAME_TYPE.LOBBY_OMAHA_GAME})
	end)
	bee.addClick(self.ItemAllIn, function()
		Game:playSound("ui_button_confirm")
		bee.logEvent("lobby-format-game", 2)
        UiManager:showUI("OmahaBlinds", {gameType = GAME_GAME_TYPE.LOBBY_HOLDEM_ALLIN})
	end)
end

function P:onStart()
	bee.invoke(self.GoldItem, "setItemId", GPropId.Gold)
	self:evt_refreshTopInfo()

	GuideManager:startSystemGuide(22001, 0.65)

	for i = 0, self.GameList.transform.childCount - 1 do
		self.GameList.transform:GetChild(i).gameObject:SetActive(false)
		self:once(0.1 * i, function()
			self.GameList.transform:GetChild(i).gameObject:SetActive(true)
		end)
	end
end

function P:evt_refreshTopInfo()
    bee.invoke(self.GoldItem, "setCount", _N2(PlayerModel:getGold()))
end

return P