local P = class("PlayerHeadBase", UiBase)

local GIFT_TAG = 10
local VIBRATION_ET = 7


function P:ctor()
	P.super.ctor(self)
	self.show_index = 0
	self.profitAniScale = 2
	self.profitAniOffsetY = 0
	self.emojiScale = 1
	self.ringScale = 1
	self.bShowingMsg = false
	self.voiceTimer = nil
	self.giftTimer = nil
	self.tmp_nodes = {}
	self._needScalePlayer = nil
end

function P:setParams(params)
	self.data = params.data
	self.seatid = params.seatid
	self.tableLayer = params.tableLayer
end

function P:onAwake()
	P.super.onAwake(self)

	self.BgRole = self:find("BgRole")
	self.BgName = self:find("BgName", self.BgRole)
	self.ImageTag = self:find("ImageTag")
	self.ImageUserType = self:find("ImageUserType", self.BgName)
	self.TextName = self:find("TextName", self.BgName)
	self.TextLevel = self:find("TextLevel", self.BgName)
	self.BgChip = self:find("BgChip", self.BgRole)
	self.TextChip = self:find("TextChip", self.BgChip)
	self.ImageBg = self:find("ImageBg", self.BgRole)
	self.Eff_poker_role_sg = self:find("Eff_poker_role_sg", self.BgRole)
	
	self.Ani_role = self:find("Ani_role", self.BgRole)
	self.ImageRole = self:find("Ani_role/ImageRole", self.BgRole)
	self.ImageTitle = self:find("ImageTitle", self.BgRole)
	self.BgChat = self:find("BgChat")
	self.BgChatPosition = self.BgChat.transform.localPosition
	self.CountDown = self:find("Eff_Countdown")
	self.ImageCD = self:find("ImageCD", self.CountDown)
	self.TextCD = self:find("TextCD", self.CountDown)
	self.BgFold = self:find("BgFold")

	self.RoleAnimator = self.Ani_role:GetComponent("Animator")
	self.RoleAnimator:Play("UI_poker_Role_idle")
end

function P:getSeatId()
	return self.seatid
end

function P:setSeatId(seatid)
	self.seatid = seatid
end

function P:getShowIndex()
	return self.show_index
end

function P:setShowIndex(index, self_index, infoIndex)
	self.show_index = index
	self.info_index = infoIndex
	self.BgChat.transform.localPosition = index >= self_index and self.BgChatPosition or bee.v3(-self.BgChatPosition.x, self.BgChatPosition.y)
	local s = self.BgChat.transform.localScale
	s.x = index >= self_index and math.abs(s.x) or - math.abs(s.x)
	self.BgChat.transform.localScale = s
	self:find("Eff_emoji_pop_up/Chat_Ani/ImageChat/TextChat", self.BgChat).transform.localScale = s
	self:find("Eff_emoji_pop_up/Chat_Ani/ImageEmoji/ImageEmoji", self.BgChat).transform.localScale = s
	if self.ImageTag then
		local pos = self.ImageTag.transform.localPosition
		if index >= self_index then
			pos.x = math.abs(pos.x)
		else
			pos.x = -math.abs(pos.x)
		end
		self.ImageTag.transform.localPosition = pos
	end
end

function P:reset()
	self:clearTmpNode()
	-- self:removeGift()
	self:stopProgress()
	-- self:stopVoicePlay()
	self:hideChatMsg()
	self:resetWinPotSpr()
	self:hideFightFx()
	self:refreshFold()
end

function P:refreshUI()
	local info = self.data:getPlayer(self.seatid)
	self:updateHeadInfo(info)
	self:refreshName(info)
	self:refreshChip(info)
	self:resetWinAnmi()
	self:hideFightFx()
	self:hideChatMsg()
	-- self:refreshFold()
end

function P:clearTmpNode()
	for _, v in ipairs(self.tmp_nodes) do
		if not tolua.isnull(v) then
			v:removeFromParent()
		end
	end
	self.tmp_nodes = {}
end

function P:isMe()
	local info = self.data:getPlayer(self.seatid)
	return info and info.uid == PlayerModel:getUid()
end

function P:getUid()
	if not self.data then return 0 end
	local info = self.data:getPlayer(self.seatid)
	return info and info.uid
end

function P:refreshName(info)
	if not self.TextName or not info then return end
	if not self._nameWidth then
		self._nameWidth = 460
	end
	bee.setTextCut(self.TextName, info.name, self._nameWidth)
	bee.setText(self.TextLevel, info.level)
	local d = tpl_level[info.level] or tpl_level[1]
	bee.setIcon(self:find("ImageLevel", self.BgName), d.icon)
	if self.ImageUserType then
		if USER_TYPE.Developer == info.user_type then
			self.ImageUserType:SetActive(true)
			bee.setIcon(self.ImageUserType, "InGame[ingame_player_other03_developer]")
		elseif USER_TYPE.Streamer == info.user_type then
			self.ImageUserType:SetActive(true)
			bee.setIcon(self.ImageUserType, "InGame[ingame_player_other02_streamer]")
		else
			self.ImageUserType:SetActive(false)
		end
	end
	if self.ImageTag then
		self.ImageTag:SetActive(false)
	end
end

function P:refreshLevel(is_level_up)
	local info = self.data:getPlayer(self.seatid)
	if info then
		bee.setText(self.TextLevel, info.level)
		local d = tpl_level[info.level] or tpl_level[1]
		bee.setIcon(self:find("ImageLevel", self.BgName), d.icon)
		if is_level_up then
			local eft = GameModel.layer:playUIEffect("Prefab/PKTable/Eff_poker_lvup", GameModel.layer.transform, nil, 3)
			eft.transform.position = self:find("ImageLevel", self.BgName).transform.position
		end
	end
end

function P:refreshChip(info, animDt, refreshWhenNoTween)
	if not self.TextChip then return end
	if refreshWhenNoTween then
		if self._showChipsTween then
			bee.setText(self.TextChip, self.data:getBetChipsStr(info.chips))
			return
		end
	end
	if self._showChipsTween then
		self._showChipsTween:Kill()
		self._showChipsTween = nil
	end
	if animDt and animDt > 0 and self._showChips then
		local chips = info.chips or 0
		self._showChipsTween = bee.Tween.toFloat(self._showChips, chips, animDt, function(v)
			if not bee.isNull(self.TextChip) then
				bee.setText(self.TextChip, self.data:getBetChipsStr(math.floor(v)))
			end
			if v == chips then
				self._showChipsTween = nil
			end
		end)
	else
		bee.setText(self.TextChip, self.data:getBetChipsStr(info.chips))
	end
	self._showChips = info.chips or 0
	self.BgName:SetActive(true)
end

function P:refreshFold()
	local info = self.data:getPlayer(self.seatid)
	if info then
		self.BgFold:SetActive(info.is_fold)
		if info.is_fold then
			self.BgFold.transform.localScale = bee.v3(0.7, 0.7, 0.7)
			self.BgFold.transform.localPosition = bee.v3(0, self:isMe() and 300 or 230)
			if self._roleSpineNode and not info:isMe() then
				bee.once(-1, function()
					if info.is_fold and not bee.isNull(self._roleSpineNode) then
						bee.invoke(self._roleSpineNode, "pauseAnim")
					end
				end)
			end
		end
	end
end

function P:showChip(isShow)
	self.BgName:SetActive(isShow)
end

function P:isShowingMsg()
	return self.bShowingMsg
end

function P:isChatFlipped()
	local show_index = self:getShowIndex()
	local self_index = self.data:getSelfShowIndex()
	return show_index >= self_index
end

function P:getMidWorldPos()
	return self.transform.position
end

function P:showVoiceTag(isShow)
	if isShow == false then
		self.ImageVoice:SetActive(false)
		return
	end
	self.ImageVoice:SetActive(true)
	local flipped = self:isChatFlipped()
	self.ImageVoice:setFlippedX(flipped)
	self.LabelVoice:setFlippedX(flipped)
end

function P:stopVoicePlay()
	self.bShowingMsg = false
	self:cancelVoiceTimer()
	self.ImageVoice:SetActive(false)
end

function P:cancelVoiceTimer()
	if self.voiceTimer and not tolua.isnull(self.voiceTimer) then
		self.rootNode:stopAction(self.voiceTimer)
		self.voiceTimer = nil
	end
end

function P:updateTimerLb(duration, callback)
	local timerCount = 0
	local function onTimerUpdate()
		timerCount = timerCount + 1
		if duration == timerCount then
			self:cancelVoiceTimer()
			self.ImageVoice:SetActive(false)
			self.bShowingMsg = false
			callback()
		end
	end
	bee.setText(self.LabelVoice, duration .. "\"")
	self.voiceTimer = self.rootNode:schedule(onTimerUpdate, 1)
	self.bShowingMsg = true
end

function P:showChatMsg(content)
	self.BgChat:SetActive(false)
	self.BgChat:SetActive(true)
	self:find("Eff_emoji_pop_up/Chat_Ani/ImageChat", self.BgChat):SetActive(true)
	self:find("Eff_emoji_pop_up/Chat_Ani/ImageEmoji", self.BgChat):SetActive(false)
	bee.setText(self:find("Eff_emoji_pop_up/Chat_Ani/ImageChat/TextChat", self.BgChat), content)

	scheduler:removeTarget(self.BgChat)
	bee.once(4, function()
		self.BgChat:SetActive(false)
	end, self.BgChat)
end

function P:hideChatMsg()
	self.BgChat:SetActive(false)
end

function P:showEmojiMsg(id)
	self.BgChat:SetActive(false)
	self.BgChat:SetActive(true)
	self:find("Eff_emoji_pop_up/Chat_Ani/ImageChat", self.BgChat):SetActive(false)
	self:find("Eff_emoji_pop_up/Chat_Ani/ImageEmoji", self.BgChat):SetActive(true)
	bee.setIcon(self:find("Eff_emoji_pop_up/Chat_Ani/ImageEmoji/ImageEmoji", self.BgChat), tpl_emoji[id].emoji)

	scheduler:removeTarget(self.BgChat)
	bee.once(4, function()
		self.BgChat:SetActive(false)
	end, self.BgChat)
end

function P:hideEmojiMsg()
	self.BgChat:SetActive(false)
end

function P:onGetProfit(chips)
	self:playProfitAni()
end

function P:playProfitAni()
	-- local animation
	-- if self.winPotSpr then
	-- 	animation = display.getAnimation("WinPot")
	-- else
	-- 	local ani, spr = display.getAnimationAndSprite("WinPot")
	-- 	animation = ani
	-- 	spr:setScale(self.profitAniScale)
	-- 	spr:setPositionY(self.profitAniOffsetY)
	-- 	self.winPotSpr = spr
	-- 	self.rootNode:addChild(self.winPotSpr, -1)
	-- end
	-- self:resetWinPotSpr()
	-- self.winPotSpr:SetActive(true)

	-- self.winPotSpr:playAnimationOnce(animation, {onComplete = function ()
	-- 	self.winPotSpr:SetActive(false)
	-- end})
end

function P:resetWinPotSpr()
	if self.winPotSpr then
		self.winPotSpr:SetActive(false)
		-- self.winPotSpr:stopAllActions()
	end
end

function P:showSitdownAni(only_one)
	if self.data.isShowUserInfo and not self:isMe() then
		local isShow = self.data:isShowUserInfo(self.seatid)
		if not isShow then
			return
		end
	end

	local effect = self:playSitdownEffect(only_one)
	if effect or only_one then
		return
	end
end

function P:showHeadRing(vip_level, frame)
	local item = G.ccsMgr:createWidget("HeadRing")
	item.rootNode:setPosition(0, self.profitAniOffsetY)
	item.rootNode:setScale(self.ringScale)
	if frame and frame >= 0 then
		item.rootNode.subChildren["ImageRing"]:SetActive(frame == 0 or frame > 4)
		if item.rootNode.subChildren["SpriteWing"] then
			item.rootNode.subChildren["SpriteWing"]:SetActive(false)
		end
		item:playAnimation("show", function()
			item.rootNode:removeFromParent()
		end)
	end
	self.rootNode:addChild(item.rootNode)
	self.tmp_nodes[#self.tmp_nodes + 1] = item.rootNode
end

function P:startProgress(duration, actionTime, vibrationEt)
	self:stopProgress()
	if GuideManager:isInGuide() then
		return
	end
	self.CountDown:SetActive(true)
	local thinkTime = self.data:getThinkTime()
	self:find("frame_add", self.CountDown):SetActive(thinkTime > 0)
	if thinkTime > 0 then
		bee.setTextOrigin(self:find("frame_add/TextCD", self.CountDown), "+" .. math.ceil(thinkTime))
	end

	bee.setText(self:find("Text", self.CountDown), _T("LAB_COUNTDOWN"))
	if self._needScalePlayer then
		self.RoleAnimator:Play("UI_poker_Role_dc")
	end

	actionTime = actionTime or self.data:getActionTime()
	duration = duration or actionTime
	if duration > 0 then
		bee.setTextOrigin(self.TextCD, math.round(duration))
		local shockFlag = duration >= 6 and self:isMe()
		self._cdTimer = self:repeatN(math.round(duration), 1, function()
			duration = duration - 1
			bee.setTextOrigin(self.TextCD, math.round(duration))
			if shockFlag and duration <= 5 then
				shockFlag = false
				bee.vibrate(tpl_vibrate.shock_warning)
			end
			if duration <= 0 then
				self:tryShowThinkTime()
			end
		end)
		self._cdTween = bee.Tween.toFloat(duration / actionTime, 0, duration, function(v)
			bee.setFillAmount(self.ImageCD, v)
			if v <= 0 then
				self._cdTween = nil
			end
		end)
		CS.DoTweenHelper.TweenEase(self._cdTween, DT.Ease.Linear)
	else
		bee.setTextOrigin(self.TextCD, 0)
		bee.setFillAmount(self.ImageCD, 0)
		self:tryShowThinkTime()
	end
	local bgEft = "Prefab/PKTable/eff_poker_role_yellow"
	if self:isMe() then
		bee.vibrate(tpl_vibrate.shock_action)
	else
		local player = self.data:getPlayer(self.seatid)
		if player.user_type == USER_TYPE.Developer then
			bgEft = "Prefab/PKTable/eff_poker_role_greed"
		elseif player.user_type == USER_TYPE.Streamer then
			bgEft = "Prefab/PKTable/eff_poker_role_blue"
		else
			bgEft = "Prefab/PKTable/eff_poker_role_purple"
		end
	end
	self._bgEft = GameModel.layer:playUIEffect(bgEft, self.ImageBg.transform, bee.v3zero, -1)

	if not bee.isNull(self.Eff_poker_role_sg) then
		self.Eff_poker_role_sg:SetActive(true)
	end
end

function P:tryShowThinkTime()
	local thinkTime = self.data:getThinkTime()
	if thinkTime > 0 then
		thinkTime = math.ceil(thinkTime)
		local frame_add = self:find("frame_add", self.CountDown)
		local TextCD = self:find("TextCD", frame_add)
		bee.setTextOrigin(TextCD, (thinkTime > 0 and "+" or "") .. thinkTime)

		self._cdTimer = self:repeatN(thinkTime, 1, function()
			thinkTime = thinkTime - 1
			bee.setTextOrigin(TextCD, (thinkTime > 0 and "+" or "") .. thinkTime)
		end)
	end
end

function P:stopProgress(isAnim)
	self.CountDown:SetActive(false)
	if self._needScalePlayer and not self._isInScraping then
		self.RoleAnimator:Play("UI_poker_Role_idle")
	end
	if self._cdTimer then
		scheduler:removeTag(self._cdTimer)
		self._cdTimer = nil
	end
	if self._cdTween then
		self._cdTween:Kill()
		self._cdTween = nil
	end
	if not bee.isNull(self._bgEft) then
		GameModel.layer:putEffectItem(self._bgEft)
		self._bgEft = nil
	end
	if not bee.isNull(self.Eff_poker_role_sg) then
		self.Eff_poker_role_sg:SetActive(false)
	end
end

function P:vibration()
end

function P:actionWarn()
end

function P:emphasizeHead()
	-- self.headController.rootNode:stopAllActions()
	-- local seq = cc.Sequence:create(cc.ScaleTo:create(0.1, 1.2), cc.ScaleTo:create(0.1, 1))
	-- self.headController.rootNode:runAction(seq)
end

function P:sendGiftCallback()
	local params = {seatid = self.seatid, tableInfo = self.data}
	G.ccsMgr:showCCSUI("SendGiftInterface", params)
	self.data:sendLocalLog("game_%s_gift")
end

function P:headClickCallback()
	local info = self.data:getPlayer(self.seatid)
	if not info then return end
	local params = {info = info, tableInfo = self.data}
	G.ccsMgr:showCCSUI("PlayerHeadDialog", params)
	if self:isMe() then
		self.data:sendLocalLog("game_%s_profileclick_self")
	else
		self.data:sendLocalLog("game_%s_profileclick_others")
	end
end

function P:showExpChange(msg)
end

function P:refreshBlockIcon(uid, flag)
	if uid == self:getUid() then
		if flag then
			--self.headController:updateIcon(nil, uid)
		else
			local info = self.data:getPlayer(self.seatid)
			--self.headController:updateIcon(info.icon_url, uid)
		end
	end
end

function P:updateHeadInfo(info)
	info = info or self.data:getPlayer(self.seatid)
	if info then
		-- self.headController:updateHeadInfo(info.icon_url, info.vip_level, info.gender, info.uid, info.frame)
	end
end

function P:resetWinAnmi()
	if self.winUi then
		self.winUi:SetActive(false)
		self.winUi:stopAnimation()
		self.winUi.rootNode:setScale(self:isMe() and 1.0 or 0.8)
	end
end

function P:showWinnerAnmi()
end

function P:showFightFx()
end

function P:hideFightFx()
end

function P:playSitdownEffect(only_one)
	return false
end

