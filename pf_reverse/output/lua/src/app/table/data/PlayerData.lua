local P = class("PlayerData")

function P:ctor(index)
    self.index = index
    self.seatid = index
    self.on_seat = false
    self.chips = 0
    self.begin_chips = 0
    self.default_byin = 0
    
    self.uid = 0
    self.name = "Player" .. self.index
    self.avatar = ""
    self.gender = ""
    self.vip_level = 0
    self.level = 1
    self.frame = 0
    self.title = 0

    self.has_card = false
    self.is_fold = false
    self.hand_cards = nil
    self.bet_chip = 0
    self.bet_change = 0
    self.action_type = POKER_ACTION.SITED
    self.last_action_type = POKER_ACTION.NONE
    self.is_allin = false
    self.wait_blind_type = 2

    self.seat_reserve = false   -- setting out

    self.win_rate = 0 -- 胜率，百分比表示
    self.last_win_rate = 0

    self.enter_buff_id = 0
    self.enter_buff_time = 0
end

function P:resetInfo(info, data)
	self.chips = info.hand_chips or 0
    self.default_byin = info.default_byin or 0
	self.seat_reserve = info.seat_reserve or false

	self.bet_chip = info.destop_chips or 0
    self.win_rate = 0
    self.last_win_rate = 0
    self.begin_chips = info.begin_chips or self.chips
    self.last_action_type = info.last_action_type
    self.is_allin = info.is_allin
	if not info.player or not info.player.uid or info.player.uid <= 0 then
		self.on_seat = false
        self.action_type = POKER_ACTION.NONE
		return
	end
	self.on_seat = true

    if data:isPlaying() then
	    self.action_type = info.action_type
    else
        self.action_type = POKER_ACTION.SITED
    end
	self.has_card = info.has_card
	if GF.isFoldAction(self.action_type) or (self.action_type == POKER_ACTION.NONE and self.last_action_type == POKER_ACTION.FOLD) then
		self.is_fold = true
	else
		self.is_fold = false
	end
	if info and info.card1 and info.card1 > 0 and info.card2 and info.card2 > 0 then
		self.hand_cards = self.hand_cards or {}
		self.hand_cards[1] = info.card1
		self.hand_cards[2] = info.card2
        if info.card3 and info.card3 > 0 then
            self.hand_cards[3] = info.card3
        end
        if info.card4 and info.card4 > 0 then
            self.hand_cards[4] = info.card4
        end
    else
        self.hand_cards = nil
	end
	self.reby_left_time = info.reby_left_time
	self.reby_left_time_st = os.time()
    self.wait_blind_type = info.wait_blind_type
end

function P:resetBriefInfo(brief)
    if brief then
		self.uid = brief.uid or 0
		self.name = brief.name or ""
		self.avatar = brief.avatar
		self.frame = brief.frame
        self.level = brief.level
        self.title = brief.title
        self.role_id = brief.role_id
        self.skin_id = brief.skin_id
        self.user_type = brief.user_type
        if brief.animations then
            for k, animInfo in pairs(brief.animations) do
                if animInfo.ftype == ACTION_TYPE.AllInEff then
                    self.allin_eff = animInfo.item_id
                elseif animInfo.ftype == ACTION_TYPE.NameplateEff then
                    self.nameplate_eff = animInfo.item_id
                end
            end
        end
    else
        self.uid = 0
        self.name = "Player" .. self.index
        self.avatar = 0
        self.frame = 0
        self.level = 1
        self.title = 0
        self.role_id = 0
        self.skin_id = 0
        self.user_type = 0
        self.allin_eff = 0
        self.nameplate_eff = 0
    end
end

function P:resetSelfInfo()
	self.uid = PlayerModel:getUid()
    if PlayerModel:getName() ~= "" then
	    self.name = PlayerModel:getName()
	    self.avatar = PlayerModel:getAvatar()
	    self.gender = PlayerModel:getGender()
        self.vip_level = 0
        self.frame = PlayerModel:getFrame()
    end
end

-- 清除手牌
function P:clearCard()
    self.has_card = false
    self.hand_cards = nil
    self.is_fold = false
    self.bet_chip = 0
    self.bet_change = 0

    -- self.action_type = POKER_ACTION.WAIT
    self.action_type = POKER_ACTION.SITED
    self.is_allin = false
end

function P:leaveFold()
    self.has_card = false
    self.hand_cards = nil
    self.is_fold = true
    self.action_type = POKER_ACTION.LEAVE_FOLD
    self.is_allin = false
    self.on_seat = false
end

-- 获取手牌牌力
function P:getHandsValue()
    if self.hand_cards and self.hand_cards[1] and self.hand_cards[2] then
        return GF.getCardValue(self.hand_cards[1], self.hand_cards[2])
    end
    return 0
end

function P:getPlayData()
    return {
        has_card = self.has_card,
        is_fold = self.is_fold,
        hand_cards = self.hand_cards,
        bet_chip = self.bet_chip,
        bet_change = self.bet_change,
        action_type = self.action_type,
        chips = self.chips,
    }
end

function P:setPlayData(d)
    self.has_card = d.has_card
    self.is_fold = d.is_fold
    self.hand_cards = d.hand_cards
    self.bet_chip = d.bet_chip
    self.bet_change = d.bet_change
    self.action_type = d.action_type
    self.chips = d.chips
end

function P:isAllin()
    return GameModel.data:isPlaying() and self.has_card and (self.action_type == POKER_ACTION.ALLIN or self.is_allin)
end

function P:isMe()
    return self.uid == PlayerModel:getUid()
end

