local P = class("GameRoom")

function P:ctor(boot, game_type, byin_chips)
    self.roomid = 1
    self.game_type = game_type or GAME_GAME_TYPE.LOBBY_HOLDEM_GAME
    self.old_room_id = 0
    self.room_info = {
        roomid = 1,
        sb = boot / 2,
        bb = boot,
        ante = 0,
        min_byin = byin_chips,
        action_time = 15,
        seat_num = 6,
        feetype = 0,
        feepoint = 0,
        default_byin = byin_chips,
        cap = 10,
        pool_limit = false,
        max_byin = byin_chips,
        room_mode = GAME_ROOM_MODE.LOBBY,
        room_type = GAME_ROOM_TYPE.HOLDEM,
        room_sub_type = GAME_SUB_TYPE.RGL,
        game_type = game_type or GAME_GAME_TYPE.LOBBY_HOLDEM_GAME,
        lobby_coin = GPropId.Gold,
        lobby_room_lvl = 1,
    }
    self.table_status = {
        is_playing = true,
        action_idx = -1,
        d_idx = -1,
        sb_idx = -1,
        bb_idx = -1,
        seat = {},
        pool = {},
        stage = 0,
        board = {},
        tid = 0,
        hand_id = "",
        is_show_card = false,   -- // 是否比牌阶段
        gameid = "",
    }
    self.room_status = {}
    self.playing_status = {
        card1 = 1,
        card2 = 2,
        card3 = 8,
        card4 = 9,
        action_seatid = 3,-- // 这个没用
        call_need_chips = 4,
        min_chipin = 5,
        max_chipin = 6,
        action_time = 7,
        pre_action_type = 10,
        pre_action_chips = 11,
    }
    self.friend_room_info = {}
    self.client_str = ""

    table.insert(self.table_status.seat, self:createSeat(0))
    table.insert(self.table_status.seat, self:createSeat(1))
    table.insert(self.table_status.seat, self:createSeat(2))
    table.insert(self.table_status.seat, self:createSeat(3))
    table.insert(self.table_status.seat, self:createSeat(4))
    table.insert(self.table_status.seat, self:createSeat(5))
end

function P:createSeat(seatid)
    return {
        seatid = seatid,
        action_type = 0,
        player = {
            uid = 0,
            name = "",
            avatar = 0,
            frame = 0,
            level = 1,
            title = 0,
            role_id = 0,
            skin_id = 0,
            user_type = 0,
        },
        hand_chips = 0,
        destop_chips = 0,
        has_card = false,
        seat_reserve = false,
        wait_blind = false,
        reby_left_time = 0,
        card1 = 0,
        card2 = 0,
        card3 = 0,
        card4 = 0,
        default_byin = 0,
        begin_chips = 0,
    }
end

function P:SitDownREQ(req)
    local seat = self.table_status.seat[req.seatid + 1]
    seat.default_byin = req.chips
    seat.begin_chips = req.chips
    seat.hand_chips = req.chips
    seat.destop_chips = 0
    seat.action_type = POKER_ACTION.SITED
    if req.player then
        for k, v in pairs(req.player) do
            seat.player[k] = v
        end
    end
    return {
        code = 0,
        seatid = seat.seatid,
        chips = req.chips,
    }
end

function P:getSeat(seatid)
    for _, v in ipairs(self.table_status.seat) do
        if v.seatid == seatid then
            return v
        end
    end
    return nil
end

-- 获取从 seatid 开始的可行动的玩家列表
function P:getActionSeats(seatid)
    local rets = {}
    for i = 1, #self.table_status.seat do
        local idx = seatid + i
        if idx > #self.table_status.seat then
            idx = idx - #self.table_status.seat
        end
        if self.table_status.seat[idx].player.uid > 0 then
            table.insert(rets, self.table_status.seat[idx])
        end
    end
    return rets
end

-- 创建一副牌
function P:buildCards()
    local cards = {}
    for i = 2, 14 do
        for j = 1, 4 do
            table.insert(cards, {i, j})
        end
    end
    table.shuffle(cards)
    return cards
end

-- 从 cards 里发一张牌
function P:dealCard(cards, number, suit)
    local c = nil
    for k, v in ipairs(cards) do
        if v[1] == number and (not suit or suit == v[2]) then
            c = GF.getCardCode(v[1], v[2])
            table.remove(cards, k)
            break
        end
    end
    if not c then
        print("=== gggg", number, suit, debug.traceback())
        printError("GameRoom deal nil card")
    end
    return c
end

-- 获取引导牌 我的手牌，ai手牌，公共牌
function P:getGuideCards()
    local cards = {}

    local deals = self:buildCards()
    cards[#cards + 1] = {
        {self:dealCard(deals, 14), self:dealCard(deals, 14)},   -- AA
        {self:dealCard(deals, 13), self:dealCard(deals, 13)},   -- KK
        {self:dealCard(deals, 13), self:dealCard(deals, 14), self:dealCard(deals, 14), self:dealCard(deals, 12), self:dealCard(deals, 13)},
    }

    deals = self:buildCards()
    cards[#cards + 1] = {
        {self:dealCard(deals, 14), self:dealCard(deals, 14)},   -- AA
        {self:dealCard(deals, 12), self:dealCard(deals, 12)},   -- QQ
        {self:dealCard(deals, 11), self:dealCard(deals, 13), self:dealCard(deals, 14), self:dealCard(deals, 14), self:dealCard(deals, 12)},
    }
    
    deals = self:buildCards()
    cards[#cards + 1] = {
        {self:dealCard(deals, 13), self:dealCard(deals, 13)},   -- KK
        {self:dealCard(deals, 14), self:dealCard(deals, 14)},   -- AA
        {self:dealCard(deals, 14), self:dealCard(deals, 13), self:dealCard(deals, 13), self:dealCard(deals, 12), self:dealCard(deals, 12)},
    }
    
    deals = self:buildCards()
    local suit = math.random(1, 4)
    cards[#cards + 1] = {
        {self:dealCard(deals, 13), self:dealCard(deals, 13)},   -- KK
        {self:dealCard(deals, 14, suit), self:dealCard(deals, 12, suit)},   -- AQs
        {self:dealCard(deals, 14), self:dealCard(deals, 13), self:dealCard(deals, 13), self:dealCard(deals, 12), self:dealCard(deals, 11)},
    }
    
    deals = self:buildCards()
    cards[#cards + 1] = {
        {self:dealCard(deals, 12), self:dealCard(deals, 12)},   -- QQ
        {self:dealCard(deals, 14), self:dealCard(deals, 14)},   -- AA
        {self:dealCard(deals, 12), self:dealCard(deals, 13), self:dealCard(deals, 12), self:dealCard(deals, 14), self:dealCard(deals, 11)},
    }
    
    deals = self:buildCards()
    cards[#cards + 1] = {
        {self:dealCard(deals, 12), self:dealCard(deals, 12)},   -- QQ
        {self:dealCard(deals, 13), self:dealCard(deals, 13)},   -- KK
        {self:dealCard(deals, 12), self:dealCard(deals, 13), self:dealCard(deals, 12), self:dealCard(deals, 14), self:dealCard(deals, 11)},
    }
    
    deals = self:buildCards()
    suit = math.random(1, 4)
    cards[#cards + 1] = {
        {self:dealCard(deals, 12), self:dealCard(deals, 12)},   -- QQ
        {self:dealCard(deals, 14, suit), self:dealCard(deals, 13, suit)},   -- KK
        {self:dealCard(deals, 12), self:dealCard(deals, 13), self:dealCard(deals, 12), self:dealCard(deals, 14), self:dealCard(deals, 11)},
    }
    
    -- deals = self:buildCards()
    -- cards[#cards + 1] = {
    --     {self:dealCard(deals, 11), self:dealCard(deals, 11)},   -- JJ
    --     {self:dealCard(deals, 13), self:dealCard(deals, 13)},   -- KK
    --     {self:dealCard(deals, 13), self:dealCard(deals, 14), self:dealCard(deals, 14), self:dealCard(deals, 11), self:dealCard(deals, 11)},
    -- }

    -- deals = self:buildCards()
    -- suit = math.random(1, 4)
    -- cards[#cards + 1] = {
    --     {self:dealCard(deals, 11), self:dealCard(deals, 11)},   -- JJ
    --     {self:dealCard(deals, 14, suit), self:dealCard(deals, 13, suit)},   -- AKs
    --     {self:dealCard(deals, 11), self:dealCard(deals, 12), self:dealCard(deals, 14), self:dealCard(deals, 14), self:dealCard(deals, 11)},
    -- }

    deals = self:buildCards()
    suit = math.random(1, 4)
    cards[#cards + 1] = {
        {self:dealCard(deals, 14, suit), self:dealCard(deals, 13, suit)},   -- AKs
        {self:dealCard(deals, 14), self:dealCard(deals, 14)},   -- AA
        {self:dealCard(deals, 12, suit), self:dealCard(deals, 11, suit), self:dealCard(deals, 10, suit), self:dealCard(deals, 14), self:dealCard(deals, 13)},
    }

    deals = self:buildCards()
    suit = math.random(1, 4)
    local suit2 = suit + 1
    if suit2 == 5 then suit2 = 1 end
    cards[#cards + 1] = {
        {self:dealCard(deals, 14, suit), self:dealCard(deals, 13, suit)},   -- AKs
        {self:dealCard(deals, 14, suit2), self:dealCard(deals, 13, suit2)},   -- AKs
        {self:dealCard(deals, 12, suit), self:dealCard(deals, 11, suit), self:dealCard(deals, 10, suit), self:dealCard(deals, 14), self:dealCard(deals, 13)},
    }

    deals = self:buildCards()
    suit = math.random(1, 4)
    cards[#cards + 1] = {
        {self:dealCard(deals, 14, suit), self:dealCard(deals, 12, suit)},   -- AQs
        {self:dealCard(deals, 14), self:dealCard(deals, 14)},   -- AA
        {self:dealCard(deals, 13, suit), self:dealCard(deals, 11, suit), self:dealCard(deals, 10, suit), self:dealCard(deals, 14), self:dealCard(deals, 13)},
    }

    deals = self:buildCards()
    suit = math.random(1, 4)
    local suit2 = suit + 1
    if suit2 == 5 then suit2 = 1 end
    cards[#cards + 1] = {
        {self:dealCard(deals, 14, suit), self:dealCard(deals, 12, suit)},   -- AQs
        {self:dealCard(deals, 14, suit2), self:dealCard(deals, 13, suit2)},   -- AKs
        {self:dealCard(deals, 13, suit), self:dealCard(deals, 11, suit), self:dealCard(deals, 10, suit), self:dealCard(deals, 14), self:dealCard(deals, 13)},
    }

    deals = self:buildCards()
    suit = math.random(1, 4)
    local c1 = self:dealCard(deals, 14, suit)
    cards[#cards + 1] = {
        {self:dealCard(deals, 13, suit), self:dealCard(deals, 12, suit)},   -- KQs
        {self:dealCard(deals, 14), self:dealCard(deals, 14)},   -- AA
        {c1, self:dealCard(deals, 11, suit), self:dealCard(deals, 10, suit), self:dealCard(deals, 14), self:dealCard(deals, 13)},
    }

    deals = self:buildCards()
    suit = math.random(1, 4)
    local suit2 = suit + 1
    if suit2 == 5 then suit2 = 1 end
    cards[#cards + 1] = {
        {self:dealCard(deals, 13, suit), self:dealCard(deals, 12, suit)},   -- KQs
        {self:dealCard(deals, 14, suit2), self:dealCard(deals, 13, suit2)},   -- AKs
        {self:dealCard(deals, 14, suit), self:dealCard(deals, 11, suit), self:dealCard(deals, 10, suit), self:dealCard(deals, 14), self:dealCard(deals, 13)},
    }

    -- if bee.isEditor then
    --     for _, v in ipairs(cards) do
    --         local _, t1, _ = PKHelper.getCardType(v[1], v[3])
    --         local _, t2, _ = PKHelper.getCardType(v[2], v[3])
    --         print("引导手牌结果：", _T(t1), _T(t2), GF.getCardNumberSuit(v[1][1]) .. GF.getCardNumberSuit(v[1][2]), GF.getCardNumberSuit(v[2][1]) .. GF.getCardNumberSuit(v[2][2]))
    --     end
    -- end

    return cards[math.random(#cards)]
end

function P:toData()
    return {
        code = 0,
        roomid = self.roomid,
        game_type = self.game_type,
        old_room_id = self.old_room_id,
        room_info = clone(self.room_info),
        table_status = clone(self.table_status),
        room_status = clone(self.room_status),
        playing_status = clone(self.playing_status),
        friend_room_info = clone(self.friend_room_info),
        client_str = client_str,
    }
end

return P