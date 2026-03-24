
local P = class("SeatNode", UiBase)

function P:ctor()
	P.super.ctor(self)
	self.headSelf = nil
	self.headOther = nil
	self.status = SEAT_ST.EMPTY_SIT
	self.show_index = 0
	self.seatid = 1
	self.index = 1
	self.data = nil
end

function P:setParams(params)
	P.super.setParams(self, params)
	self.seatid = params.seatid
	self.index = self.seatid
	self.data = params.data
	self.tableLayer = params.tableLayer
end

function P:onAwake()
	self.ButtonInvite = self:find("ButtonInvite")
	self.ButtonSit = self:find("Button")

	bee.addClick(self.ButtonSit, function()
		GF.sendSitDownRequest(self.seatid - 1, 0)
	end)
end

function P:onStart()
	-- self:initPlayer()
end

function P:initPlayer(from_st)
	if from_st and from_st == SEAT_ST.HAS_PLAYER then
		return
	end
	if self.playerCls then
		CU.GameObject.Destroy(self.playerCls.node)
		self.playerCls = nil
	end

	if self.status ~= SEAT_ST.HAS_PLAYER then
		return
	end

	local selfShowIndex = self.data:getSelfShowIndex()
	local head = nil
	if self:isMe() then
		head = CU.GameObject.Instantiate(self.tableLayer.PlayerHead, self.transform, false)
		head:SetActive(true)
		self.playerCls = ObjectPool:getCls(head)
	else
		if self.show_index > selfShowIndex then
			head = CU.GameObject.Instantiate(self.tableLayer.PlayerOther, self.transform, false)
		else
			head = CU.GameObject.Instantiate(self.tableLayer.PlayerOther, self.transform, false)
		end
		head:SetActive(true)
		self.playerCls = ObjectPool:getCls(head)
	end
	self.playerCls.node.transform.localPosition = bee.v3zero
	self.playerCls:setParams(self._params)

	self.playerCls:setShowIndex(self.show_index, selfShowIndex, self.info_index)
	self.playerCls:reset()
	self.playerCls.node:SetActive(true)
end

function P:refreshUI()
	local player = self.data:getPlayer(self.seatid)
	local status
	if player and player.on_seat then
		status = SEAT_ST.HAS_PLAYER
	elseif self.data:isMeOnSeat() then
		status = SEAT_ST.EMPTY_INVITE
	else
		status = SEAT_ST.EMPTY_SIT
	end
	self:setStatus(status)
end

function P:setStatus(status, from_st)
	self.status = status
	self:initPlayer(from_st)
	if status == SEAT_ST.HAS_PLAYER then
		self.playerCls:setSeatNode(self)
		self.playerCls:refreshUI()
	else
		if self.playerCls then
			CU.GameObject.Destroy(self.playerCls.node)
			self.playerCls = nil
		end
	end
end

function P:getSeatId()
	return self.seatid
end

function P:setSeatId(seatid)
	self.seatid = seatid
	self:emitFunc("setSeatId", seatid)
end

function P:setShowIndex(index, self_index, infoIndex)
	self.show_index = index
	self.info_index = infoIndex
	self:emitFunc("setShowIndex", index, self_index, infoIndex)
end

function P:getShowIndex()
	return self.show_index
end

function P:isMe()
	return self.seatid == self.data:getMyPosition()
end

function P:getMidWorldPos()
	return self:emitFunc("getMidWorldPos")
end

function P:refreshChip(player)
	if player.on_seat then
		self:emitFunc("refreshChip", player)
	end
end

function P:stopProgress(isAnim)
	self:emitFunc("stopProgress", isAnim)
end

function P:inviteCallback()
end

function P:showSitdownAni(only_one)
	self:emitFunc("showSitdownAni", only_one)
end

function P:showChip(isShow)
	self:emitFunc("showChip", isShow)
end

function P:showExpChange(msg)
	self:emitFunc("showExpChange", msg)
end

-- function P:refresh2ExpCards()
-- 	self.playerCls:refresh2ExpCards()
-- end

function P:refreshGoldProtectIcon(msg)
	self:emitFunc("refreshGoldProtectIcon", msg)
end

function P:goldProtectIconShowLight(isShow,isInit)
	self:emitFunc("goldProtectIconShowLight", isShow, isInit)
end

function P:refreshBlockIcon(uid, flag)
	self:emitFunc("refreshBlockIcon", uid, flag)
end

function P:emitFunc(funcName, ...)
	if self.playerCls and self.playerCls[funcName] then
		return self.playerCls[funcName](self.playerCls, ...)
	end
end

