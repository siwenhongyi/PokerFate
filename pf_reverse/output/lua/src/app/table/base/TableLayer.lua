local P = class("TableLayer", UiBase)

local TIP_MAX_WIDTH = 1200
local MAX_WIDTH_SIZE = bee.v2(TIP_MAX_WIDTH, 0)
local ZERO_SIZE = bee.v2(0, 0)

function P:ctor()
	P.super.ctor(self)
	self.seatPosition = {}
	self.seatController = {}
	self.seatInfoIndexes = {}	-- 座位对应的桌上信息序号
	self.allSeats = {}
	-- self.seatNum = params.seatNum
	self.seatNum = 6

	self._nodeCache = NodeCache:create()
end

function P:setParams(params)
	P.super.setParams(self, params)
	self.data = params.data
	self.seatNum = self.data:getSeatNum()
	self:initPlayerSeats()
	for k, v in pairs(self.seatController) do
		v:setParams({
			seatid = k,
			data = self.data,
			tableLayer = self,
		})
	end
	if self.dealer then self.dealer.data = self.data end
end

function P:reset()
	P.super.reset(self)
	for _, v in pairs(self.seatController) do
		v:activateTimeline()
	end
	self:showTopTips(nil)
end

function P:onAwake()
	self.BgTable = self:find("BgTable")

	self.PlayerHead = self:find("PlayerHead")
	self.PlayerOther = self:find("PlayerOther")
	self.PlayerHead:SetActive(false)
	self.PlayerOther:SetActive(false)

	self.ImageBg = self:find("ImageBg")
	self.ImageTable = self:find("ImageTable")

	self.BgTip = self:find("BgTip")
	if self.BgTip then
		self.ImageTips = self:find("Image", self.BgTip)
		self.TextTip = self:find("TextTip", self.BgTip)
		self.BgTip:SetActive(false)
	end
	self.BgTopTip = self:find("BgTopTip")
	if self.BgTopTip then
		self.ImageBgTip = self:find("Image", self.BgTopTip)
		self.TextTopTip = self:find("TextTopTip", self.BgTopTip)
		self.BgTopTip:SetActive(false)
	end
	self.BgBottomTip = self:find("BgBottomTip")
	if self.BgBottomTip then
		self.TextBottomTip = self:find("TextBottomTip", self.BgBottomTip)
		if self.TextBottomTip then
			bee.setText(self.TextBottomTip, _T("LAB_RM_WAIT_NEXT_RD"))
		end
	end

	self.EmojiLayer = self:find("EmojiLayer")
	self.EmojiBase = self:find("Emoji", self.EmojiLayer)
	self.EmojiBase:SetActive(false)

	self:initSeats()
	self:initDealer()
end

function P:onShow()
	P.super.onShow(self)

	GameModel:setData(self.data, self)
	
	self:showTips(nil)
	self:showTopTips(nil)

	self:refreshUI()
end

function P:afterShow()
	P.super.afterShow(self)
	GF.dealDeepLinkParams()

	TournamentModel:refreshMatchingTip()
end

function P:onHide()
	self._nodeCache:clearAll()
end

function P:onUpdate(dt)
	self._nodeCache:onUpdate(dt)
end

function P:initSeats()
	for i = 1, 9 do
		local seatNode = self:find("SeatNode" .. i)
		if seatNode then
			self.seatPosition[i] = seatNode.transform.position
			local params = {data = self.data, attach_controller = self, seatid = i}
			self.allSeats[i] = seatNode
			self.seatInfoIndexes[i] = i
		else
			break
		end
	end
	self:initPlayerSeats()
end

function P:refreshSeatPosition()
end

function P:initPlayerSeats()
	self:refreshSeatPosition()
	if table.nums(self.seatController) ~= self.seatNum then
		self.seatController = {}
		for k, v in ipairs(self.allSeats) do
			if k <= self.seatNum then
				self.seatController[k] = ObjectPool:getCls(v)
				v:SetActive(true)
				v.transform.localPosition = self.seatPosition[k]
			else
				v:SetActive(false)
			end
		end
	end
end

function P:initDealer()
	self.DealCardPosNode = self:find("DealCardPos", self.BgTable)
	self.dealCardPos = self.DealCardPosNode.transform.localPosition
	self.dealCardWorldPos = self.DealCardPosNode.transform.position
end

function P:refreshUI()
	self:initDealer()
	self:updateSeatShowIndex()
	for _, v in pairs(self.seatController) do
		v:refreshUI()
	end
	self:refreshVisitorNum()

	if self.data:isMeOnSeat() then
		local myPosition = self.data:getMyPosition()
		local controller = self.seatController[myPosition]
		if controller then
			controller:showSitdownAni()
		end
	end

	local cfg = tpl_card_table[DecorationModel:getCurCardTable(self.data:getIngameScheme())]
	if cfg then
		bee.setSprite(self.ImageBg, cfg.bg_image)
		bee.setSprite(self.ImageTable, cfg.image)
	end
end

function P:refreshVisitorNum()
end

function P:updateSeatShowIndex()
	local selfShowIndex = self.data:getSelfShowIndex()
	local seatNum = self.data:getSeatNum()
	local myPosition = self.data:getMyPosition()
	for k, v in pairs(self.seatController) do
		local index
		if myPosition > 0 then
			index = v.seatid - myPosition + selfShowIndex
			if index <= 0 then
				index = index + seatNum
			elseif index > seatNum then
				index = index - seatNum
			end
		else
			index = v.index
		end
		v:setShowIndex(index, selfShowIndex, self.seatInfoIndexes[index])
		v.node.transform.localPosition = self.seatPosition[index]
	end
end

function P:updateSeatNode(seatid, status, from_st)
	local controller = self.seatController[seatid]
	if not controller then return end
	controller:setStatus(status, from_st)
end

function P:updateEmptySeat(seatid, from_st)
	local status = self.data:isMeOnSeat() and SEAT_ST.EMPTY_INVITE or SEAT_ST.EMPTY_SIT
	self:updateSeatNode(seatid, status, from_st)
end

function P:getMySeat()
	if self.data:isMeOnSeat() then
		return self.seatController[self.data:getMyPosition()]
	end
	return nil
end

function P:getSelfEmojiParams(params)
	local controller = self.seatController[params.seatid + 1]
	if controller and controller.playerController then
		return controller.node, cc.p(0, controller.playerController.profitAniOffsetY), 10, controller.playerController.emojiScale
	end
end

function P:getOtherEmojiParams(params)
	local src_pos = cc.p(self.seatController[params.from + 1]:getPosition())
	local dst_pos = cc.p(self.seatController[params.to + 1]:getPosition())
	return self.node, src_pos, dst_pos, 10
end

function P:showTips(tip, duration)
	if not self.BgTip then return end
	bee.Tween.killByTarget(self.BgTip)
	if tip then
		self.BgTip:SetActive(true)
	else
		self.BgTip:SetActive(false)
		return
	end
	bee.setText(self.TextTip, _T(tip))
	
	if duration then
		self:once(duration, function()
			self.BgTip:SetActive(false)
		end)
	end
end

function P:showTopTips(tip, duration)
	if not self.BgTopTip then return end

	bee.Tween.killByTarget(self.BgTopTip)
	if tip then
		self.BgTopTip:SetActive(true)
	else
		self.BgTopTip:SetActive(false)
		return
	end
	bee.setText(self.TextTopTip, _T(tip))
	
	if duration then
		self:once(duration, function()
			self.BgTopTip:SetActive(false)
		end)
	end
end

function P:refreshGoldProtectIcon(event)
	local seat = self:getMySeat()
	if seat then
		seat:refreshGoldProtectIcon()
	end
end

function P:goldProtectIconShowLight(isShow,isInit)
	local seat = self:getMySeat()
	if seat then
		seat:goldProtectIconShowLight(isShow,isInit)
	end
end

function P:refreshGoldProtectLight(event)
	local isShow = event.isShow or false
	local seat = self:getMySeat()
	if seat then
		seat:goldProtectIconShowLight(isShow)
	end
end

function P:showGoldProtectItemTips()
end

function P:playUIEffect(name, parent, localPos, autoRemoveDt, noCache,layer)
	local eft = self._nodeCache:getItemWithName(name)
	if eft then
		if layer then
			eft.gameObject.layer=layer
			CS.Utils.SetAllChildLayer(eft.transform,layer)
		end
		if not parent then
			parent = self.transform
		end
		eft.transform:SetParent(parent, false)
		if localPos then
			eft.transform.localPosition = localPos
		end
		if -1 ~= autoRemoveDt then
			if noCache then
				CU.GameObject.Destroy(eft, autoRemoveDt or 2)
			else
				self._nodeCache:putItem(eft, autoRemoveDt or 2)
			end
		end
		return eft
	end
end

function P:putEffectItem(eft)
	self._nodeCache:putItemImm(eft)
end

-- function P:refreshUserItemBuff(event)
-- 	for _, v in pairs(self.seatController) do
-- 		v:refresh2ExpCards()
-- 	end
-- end

function P:evt_OtherEnterRoomBRC(msg)
	local user = msg.user
	if user then
		if -1 ~= user.uid and user.uid ~= PlayerModel:getUid() then
			self:showTopTips(_F("LAB_JOIN_MSG", user.name), 2)
		end
		self:refreshVisitorNum()

		local player, i = self.data:getPlayerByUid(msg.user.uid)
		if player then
			self.seatController[i]:emitFunc("refreshRole")
		end
	end
end

function P:evt_OtherLeaveRoomBRC(msg)
	self:refreshVisitorNum()
end

function P:evt_SitDownRSP(msg)
	if msg.code ~= 0 then return end
	local seatid = msg.seatid + 1
	self:updateSeatNode(seatid, SEAT_ST.HAS_PLAYER, SEAT_ST.EMPTY_SIT)
	for i, info in ipairs(self.data:getAllPlayers()) do
		if not info.on_seat then
			self:updateEmptySeat(i, SEAT_ST.EMPTY_INVITE)
		end
	end
	local selfShowIndex = self.data:getSelfShowIndex()
	local myPosition = self.data:getMyPosition()
	self:updateSeatShowIndex()

	local controller = self.seatController[seatid]
	if controller then
		controller:showSitdownAni()
	end

	if self.BgBottomTip and self.data:isPlaying() then
		self.BgBottomTip:SetActive(true)
		-- local controller = self.seatController[self.data:getMyPosition()]
		-- if controller then
		-- 	controller:showChip(false)
		-- end
	end
end

function P:evt_SitDownBRC(msg)
	local seatid = msg.status.seatid + 1
	local from_st = self.data:isMeOnSeat() and SEAT_ST.EMPTY_INVITE or SEAT_ST.EMPTY_SIT
	self:updateSeatNode(seatid, SEAT_ST.HAS_PLAYER, from_st)
	local player = self.data:getPlayer(seatid)
	self:refreshVisitorNum()

	local controller = self.seatController[seatid]
	if controller then
		if seatid ~= self.data:getMyPosition() then
			controller:showSitdownAni()
		end
	end
	GameModel:playSitdownVoice(player.skin_id)
end

function P:evt_StandUpRSP(msg)
	for i, info in ipairs(self.data:getAllPlayers()) do
		if not info.on_seat then
			self:updateEmptySeat(i, SEAT_ST.EMPTY_SIT)
		end
	end
	self:hideWaitTip()
end

function P:evt_StandUpBRC(msg)
	local seatid = msg.seatid + 1
	local player = self.data:getPlayer(seatid)
	local seat = self.seatController[seatid]
	if player and player.bet_chip > 0 and not player.is_fold then
		player:leaveFold()
		seat:foldCard()
		-- if player.has_card then
		-- end
	end
	
	self:updateEmptySeat(seatid, SEAT_ST.HAS_PLAYER)
	local selfShowIndex = self.data:getSelfShowIndex()
	if seat then
		local show_index = seat:getShowIndex()
		seat:setShowIndex(show_index, selfShowIndex, self.seatInfoIndexes[show_index])
	end
	self:refreshVisitorNum()
end


function P:showGiftAnim(seatid, src_pos, target_player, config, gift_id)
end

function P:evct_ChipsExchangeBRC(params)
	local uid = params.uid
	if uid > 0 then
		player, seatid = self.data:getPlayerByUid(uid)
	end
	if not player then
		player = self.data:getPlayer(params.seatid + 1)
	end
	if player then
		player.chips = params.chips
		if self.seatController[seatid] then
			self.seatController[seatid]:refreshChip(player)
		end
	end
end

function P:evt_ExpChangeRSP(msg)
	local info = self.data:getMyPlayerInfo()
	if info and info.level ~= msg.level then
		info.level = msg.level
		self.seatController[self.data:getMyPosition()]:emitFunc("refreshLevel", true)
	end
end

function P:evt_LevelUpBRC(msg)
	local info = self.data:getPlayerByUid(msg.uid)
	if info then
		info.level = msg.level
		self.seatController[info.seatid]:emitFunc("refreshLevel", true)
	end
end

function P:evt_FaceBRC(msg)
	if SettingModel:isHideEmoji() and (msg.seatid + 1 ~= self.data:getMyPosition() or self.data:isInObserve()) then
		return
	end
	if 0 == msg.code then
		local player = self.data:getPlayer(msg.seatid + 1)
		if player and (PlayerModel:isBlockChat(player.uid) or FriendModel:getBlockedInfo(player.uid)) then
			return
		end
		local seat = self.seatController[msg.seatid + 1]
		if seat and tpl_emoji[msg.id] then
			seat:emitFunc("showEmojiMsg", msg.id)
		end
	end
end

function P:evt_TextBRC(msg)
	if SettingModel:isHideChat() and (msg.seatid + 1 ~= self.data:getMyPosition() or self.data:isInObserve())  then
		return
	end
	local player = self.data:getPlayer(msg.seatid + 1)
	if player and (PlayerModel:isBlockChat(player.uid) or FriendModel:getBlockedInfo(player.uid)) then
		return
	end
	if tpl_chat[msg.id].language_type then
		local isIn = false
		for k,v in pairs(tpl_chat[msg.id].language_type) do
			if v == LanguageManager:getLanguage() then
				isIn = true
				break
			end
		end
		if not isIn then
			return
		end
	end
	local seat = self.seatController[msg.seatid + 1]
	if seat and tpl_chat[msg.id] then
		seat:emitFunc("showChatMsg", _T(tpl_chat[msg.id].text))
		seat:playSound(tpl_chat[msg.id].key)
	end
end

function P:evt_CustomTextBRC(msg)
	local player = self.data:getPlayer(msg.seatid + 1)
	local seat = self.seatController[msg.seatid + 1]
	if seat then
		seat:emitFunc("showChatMsg", msg.text)
	end
end

function P:evt_GetRoomDataRSP(msg)
	-- UiManager:hideUI("IngameNoticeSave")
	UiManager:hideUI("IngameAllin")
	UiManager:hideUI("IngameResult")
	self._nodeCache:clearAll()
	self:refreshUI()
end

function P:evt_ChangeTableRSP(msg)
	UiManager:hideUI("IngameAllin")
	UiManager:hideUI("IngameResult")
	self._nodeCache:clearAll()
	self:refreshUI()
end

function P:evt_FriendRoomOwnerChangeBRC(msg)
	local info, i = self.data:getPlayerByUid(msg.owner.uid)
	if info then
		self.seatController[i]:emitFunc("refreshFriendOwner", info)
	end
end

function P:evt_ChangeObserveViewRSP()
	self:evt_GetRoomDataRSP()
end

--局内交互表情
function P:evt_EmojiBRC(msg)
	if SettingModel:isHideIEmoji() and msg.uid ~= PlayerModel:getUid() then
		return
	end
	
	if PlayerModel:isBlockChat(msg.uid) or FriendModel:getBlockedInfo(msg.uid) then
		return
	end

	local sender = nil
	local receiver = nil
	for _,v in pairs(self.data.player_info) do
		if v.uid == msg.uid then
			sender = v
		end
		if v.uid == msg.to_uid then
			receiver = v
		end
	end
    self:playEmoji(sender, receiver, msg.id)
end

function P:evt_IngameEmojiTest(msg)
	local cfg = tpl_table_emoji[msg.id]
	local sendPt = self.seatController[msg.sid]
	local spt = self:find("EmojiPoint", sendPt.node)
	if spt == nil then
		spt = CS.UnityEngine.GameObject('EmojiPoint')
		spt.transform:SetParent(sendPt.node.transform, false)
		spt.transform.localPosition = bee.v3(0, 0, 0)
	end
	-- spt.transform.localPosition = bee.v3(0 + (cfg.send_offset and cfg.send_offset[1] or 0), (cfg.send_offset and cfg.send_offset[2] or 0), 0)
	
	local receiverPt = self.seatController[msg.rid]
	local rpt = self:find("EmojiPoint", receiverPt.node)
	if rpt == nil then
		rpt = CS.UnityEngine.GameObject('EmojiPoint')
		rpt.transform:SetParent(receiverPt.node.transform, false)
		rpt.transform.localPosition = bee.v3(0, 0, 0)
	end
	--rpt.transform.localPosition = bee.v3(0 + (cfg.receive_offset and cfg.receive_offset[1] or 0), (cfg.receive_offset and cfg.receive_offset[2] or 0), 0)
	
	local obj = CU.GameObject.Instantiate(self.EmojiBase)
	obj.transform:SetParent(self.EmojiLayer.transform, false)
	obj:SetActive(true)
	EmojiModel:playEmoji(obj, spt.transform.position, rpt.transform.position, msg.id)
end

function P:playEmoji(sender, receiver, id)
	local cfg = tpl_table_emoji[id]
	local senderData = self.seatController[sender.seatid].playerCls
	local sendPos = nil
	local sendEmojiPoint = senderData and self:find("EmojiPoint/OffsetPoint", senderData.node) or nil
	if sendEmojiPoint then
		local seatOffset = EmojiModel.seatOffsetPos[self.seatController[sender.seatid].show_index]
		sendEmojiPoint.transform.localPosition = cfg.send_offset and bee.v3(cfg.send_offset[1] + seatOffset[1], cfg.send_offset[2] + seatOffset[2], 0) or bee.v3zero
		sendPos = sendEmojiPoint.transform.position
	end

	local receiverData = self.seatController[receiver.seatid].playerCls
	local receivePos = nil
	local receiveEmojiPoint = receiverData and self:find("EmojiPoint/OffsetPoint", receiverData.node) or nil
	if receiveEmojiPoint then
		local seatOffset = EmojiModel.seatOffsetPos[self.seatController[receiver.seatid].show_index]
		receiveEmojiPoint.transform.localPosition = cfg.receive_offset and bee.v3(cfg.receive_offset[1] + seatOffset[1], cfg.receive_offset[2] + seatOffset[2], 0) or bee.v3zero
		receivePos = receiveEmojiPoint.transform.position
	end

	if sendPos and receivePos then
		local obj = CU.GameObject.Instantiate(self.EmojiBase)
		obj.transform:SetParent(self.EmojiLayer.transform, false)
		obj:SetActive(true)
		EmojiModel:playEmoji(obj, sendPos, receivePos, id)
	end
end

function P:hideWaitTip()
	if self.BgBottomTip then
		self.BgBottomTip:SetActive(false)
	end

	local controller = self.seatController[self.data:getMyPosition()]
	if controller then
		controller:showChip(true)
	end
end

function P:refreshWaitTip()
	if not self.BgBottomTip then
		return
	end
	if not self.data:isPlaying() or self.data:isMePlaying() then
		self:hideWaitTip()
	end
end

function P:evt_TeenDealCardsBRC()
	if self.dealer and LocalStore:isDailyTagValid("TABLE_DEALER_TIP_" .. PlayerModel:getUid()) then
		self.dealer:showChangeTip(true)
	end
end

function P:emitSeatFunc(funcName, ...)
	for _, v in pairs(self.seatController) do
		if v[funcName] then
			v[funcName](v, ...)
		end
	end
end

function P:checkSitdownAni(only_one)
	local now = bee.getServerTime()
	for seatid, v in pairs(self.seatController) do
		local player = self.data:getPlayer(seatid)
		if player and player.enter_buff_id and player.enter_buff_id > 0 and player.enter_buff_time and player.enter_buff_time > now then
			if seatid ~= self.data:getMyPosition() then
				v:showSitdownAni(only_one)
			end
		end
	end	
end

return P
