local P = class("PokerPlayerHeadOther", require("app.table.PK.heads.PKPlayerHead"))

local ACTION_TAG_DICT = {
	-- [POKER_ACTION.FOLD] = D.IMAGE.ACTION_FOLD,
	-- [POKER_ACTION.CHECK] = D.IMAGE.ACTION_CHECK,
	-- [POKER_ACTION.CALL] = D.IMAGE.ACTION_CALL,
	-- [POKER_ACTION.RAISE] = D.IMAGE.ACTION_RAISE,
	-- [POKER_ACTION.BET] = D.IMAGE.ACTION_BET,
}

function P:ctor()
	P.super.ctor(self)
	self.profitAniScale = 2
	self._needScalePlayer = true
end

function P:onAwake()
	P.super.onAwake(self)
	
	self.TextChipGreen = self:find("TextChipGreen", self.BgChip)
	self.TextChipBlue = self:find("TextChipBlue", self.BgChip)
	self.TextChipPurple = self:find("TextChipPurple", self.BgChip)
	self.TextChipGreen:SetActive(false)
	self.TextChipBlue:SetActive(false)
	self.TextChipPurple:SetActive(false)
	self.TextChip = self.TextChipGreen
end

function P:setShowIndex(index, self_index, infoIndex)
	P.super.setShowIndex(self, index, self_index, infoIndex)
	-- local x = index >= self_index and -self.originCardX or self.originCardX
	-- self.cardController:setDefaultPos(x)
end

function P:reset()
	P.super.reset(self)
	self:hideFightFx()
end

function P:refreshUI()
	local info = self.data:getPlayer(self.seatid)
	if self.TextChip then
		self.TextChip:SetActive(false)
	end
	if info.user_type == USER_TYPE.Developer then
		bee.setIcon(self:find("ImageFg", self.BgRole), "InGame[ingame_player_other_fg_01]")
		self.TextChip = self.TextChipGreen
	elseif info.user_type == USER_TYPE.Streamer then
		bee.setIcon(self:find("ImageFg", self.BgRole), "InGame[ingame_player_other_fg_02]")
		self.TextChip = self.TextChipBlue
	else
		bee.setIcon(self:find("ImageFg", self.BgRole), "InGame[ingame_player_other_fg]")
		self.TextChip = self.TextChipPurple
	end
	self.TextChip:SetActive(true)
	self._isInTopupStatus = nil

	P.super.refreshUI(self)
	
	self:refreshSittingOut()
end

function P:refreshActionUI(instant)
	P.super.refreshActionUI(self, instant)
	local info = self.data:getPlayer(self.seatid)
	self:refreshAction(info, instant)
end

function P:refreshAction(info, instant)
end

function P:startProgress(duration)
	P.super.startProgress(self, duration)
	self:refreshAction(nil)
end

function P:refreshSittingOut()
end

function P:refreshAddingChips(is_adding, chips, type)
	if self._isInTopupStatus then
		return
	end
	bee.Tween.killByTarget(self.BgStatus)
	if is_adding and self.data:getRebuyRemainTime(self.seatid) > 0 then
		self.BgStatus:SetActive(true)
		bee.setText(self:find("TextStatus", self.BgStatus), _T("LAB_BUYINGING"))
	else
		self.BgStatus:SetActive(false)
	end
	if type == "topup" then
		self._isInTopupStatus = true
		self.BgStatus:SetActive(true)
		bee.setText(self:find("TextStatus", self.BgStatus), _F("LAB_GAME_030", _N(chips or 0)))
		bee.tween(self.BgStatus)
		: delay(1)
		: onComplete(function()
			self._isInTopupStatus = nil
			self.BgStatus:SetActive(false)
		end)
		: link()
		: setTarget()
	end
end

