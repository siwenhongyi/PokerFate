local P = class("GameServer")

-- 游戏阶段
local GAME_STAGE = {
    None = 0,   -- 等待开始
    Dealer = 1, -- 移庄
    Preflop = 2,    -- 翻前
    Flop = 3,
    Turn = 4,
    River = 5,
    Show = 6,
    Win = 7,
    Action = 8, -- 行动
    RoundOver = 9,
    NextRound = 10,
}

-- 本地服务器
function P:ctor()
    self.room = nil
    self._et = 0
    self._aiet = 0  -- ai 行动思考时长
    self._aiIndex = 1   -- ai 的行动索引
    self._max_bet = 0
end

function P:QuickStartREQ(data)
    self.room = require("app.server.GameRoom"):create(data.boot, data.game_type, data.byin_chips)
    local rsp = self.room:SitDownREQ({
        seatid = 2,
        chips = data.byin_chips,
        wait_blind = true,
        player = {
            uid = PlayerModel:getUid(),
            name = PlayerModel:getName(),
            avatar = PlayerModel:getAvatar(),
            frame = PlayerModel:getFrame(),
            level = PlayerModel:getCurLevel(),
            title = PlayerModel:getTitle(),
            role_id = CharacterModel:getUsingRoleId(),
            skin_id = CharacterModel:getUsingRole():getUsingSkin(),
            user_type = 0,
        },
    })
    local d = tpl_guide_user_list[math.random(#tpl_guide_user_list)]
    self.room:SitDownREQ({
        seatid = 0,
        chips = data.byin_chips,
        wait_blind = true,
        player = {
            uid = d.id,
            name = _T(d.name),
            avatar = d.avatar,
            frame = d.frame,
            level = d.level,
            title = d.title,
            role_id = d.role_id,
            skin_id = d.skin_id,
            user_type = d.user_type,
        },
    })
    self:doResp("EnterRoomRSP", self.room:toData())
    self:doResp("SitDownRSP", rsp)

    self._updater = function(dt)
        self:onUpdate(dt)
    end
    bee.addUpdater(self._updater)

    self._stage = GAME_STAGE.None
    self._et = 2
end

function P:LeaveRoomREQ()
    Net:setRecver(nil)
    bee.removeUpdater(self._updater)
    self:doResp("LeaveRoomRSP", {
        code = 0, roomid = self.room.roomid,
    })
end

function P:ActionREQ(data)
    self._et = 0.3
    local seat = self.room:getSeat(self.room.table_status.action_idx)
    seat._is_action = true
    if data.action_type == POKER_ACTION.FOLD then
        self:doActionBRC(self.room.table_status.action_idx, data.action_type, 0)
    elseif data.action_type == POKER_ACTION.CHECK then
        self:doActionBRC(self.room.table_status.action_idx, data.action_type, 0)
    elseif data.action_type == POKER_ACTION.CALL then
        self:doActionBRC(self.room.table_status.action_idx, data.action_type, self._max_bet - seat.destop_chips)
    elseif data.action_type == POKER_ACTION.RAISE then
        self:doActionBRC(self.room.table_status.action_idx, data.action_type, data.chips)
    elseif data.action_type == POKER_ACTION.BET then
        self:doActionBRC(self.room.table_status.action_idx, data.action_type, data.chips)
    elseif data.action_type == POKER_ACTION.ALLIN then
        self:doActionBRC(self.room.table_status.action_idx, data.action_type, seat.hand_chips)
        self._et = 2
    end
    
    self:doResp("ActionRSP", {code = 0})
    self._stage = GAME_STAGE.Action
end

function P:isEveryoneAllin()
    local ret = 0
    local seats = self.room:getActionSeats(0)
    for i = 1, #seats do
        if seats[i].action_type ~= POKER_ACTION.FOLD and seats[i].hand_chips > 0 then
            ret = ret + 1
        end
    end
    return ret <= 1
end

-- 从 seatid 开始寻找行动玩家
function P:findActionIdx(seatid)
    local action_idx = self.room.table_status.action_idx
    local seats = self.room:getActionSeats(seatid)
    for i = 1, #seats do
        if seats[i].action_type ~= POKER_ACTION.FOLD and 
        (seats[i].destop_chips < self._max_bet or (not seats[i]._is_action)) and 
        seats[i].hand_chips > 0 then
            self.room.table_status.action_idx = seats[i].seatid
            return true
        end
    end
    return false
end

function P:doDealerInfoRSP()
    self._isShowHands = false
    local start_info = {}
    for _, v in ipairs(self.room.table_status.seat) do
        if v.player.uid > 0 then
            table.insert(start_info, {seatid = v.seatid, chips = v.hand_chips})
            if v.player.uid == PlayerModel:getUid() then
                self.room.table_status.bb_idx = v.seatid
            else
                self.room.table_status.d_idx = v.seatid
                self.room.table_status.sb_idx = v.seatid
            end
        end
    end
    self:doResp("DealerInfoRSP", {
        dealer = self.room.table_status.d_idx,
        small_blind = self.room.table_status.sb_idx,
        big_blind = self.room.table_status.bb_idx,
        start_info = start_info,
        gameid = "game_guide",
    })
    self._cards = self.room:getGuideCards()
    local seats = self.room:getActionSeats(0)
    for _, v in ipairs(seats) do
        if v.player.uid == PlayerModel:getUid() then
            v.card1, v.card2 = self._cards[1][1], self._cards[1][2]
        else
            v.card1, v.card2 = self._cards[2][1], self._cards[2][2]
        end
    end
end

function P:doRoundStartBRC()
    local board = {}
    if self.room.table_status.stage == POKER_ROUND.FLOP then
        for i = 1, 3 do
            self.room.table_status.board[i] = self._cards[3][i]
            board[i] = self._cards[3][i]
        end
    elseif self.room.table_status.stage == POKER_ROUND.TURN then
        self.room.table_status.board[4] = self._cards[3][4]
        board[1] = self._cards[3][4]
    elseif self.room.table_status.stage == POKER_ROUND.RIVER then
        self.room.table_status.board[5] = self._cards[3][5]
        board[1] = self._cards[3][5]
    end
    self:doResp("RoundStartBRC", {stage = self.room.table_status.stage, board = board})
    self.room.table_status.action_idx = -1
    self._max_bet = 0
    
    for _, v in ipairs(self.room.table_status.seat) do
        v._is_action = false
        if v.player.uid == PlayerModel:getUid() then
            self:doResp("HandCardRSP", {
                card1 = v.card1,
                card2 = v.card2,
            })
        end
    end
    if self.room.table_status.stage == POKER_ROUND.PRE_FLOP then
        self:doActionBRC(self.room.table_status.sb_idx, POKER_ACTION.SB, self.room.room_info.sb)
        self:doActionBRC(self.room.table_status.bb_idx, POKER_ACTION.BB, self.room.room_info.bb)
    end
end

function P:doRoundOverBRC()
    self.room.table_status.pool[1] = self.room.table_status.pool[1] or 0
    for _, v in ipairs(self.room.table_status.seat) do
        self.room.table_status.pool[1] = self.room.table_status.pool[1] + v.destop_chips
        v.destop_chips = 0
    end
    self:doResp("RoundOverBRC", {pool = clone(self.room.table_status.pool)})
end

function P:doActionBRC(seatid, action_type, chips)
    local seat = self.room:getSeat(seatid)
    seat.action_type = action_type
    if chips > 0 then
        seat.destop_chips = seat.destop_chips + chips
        seat.hand_chips = seat.hand_chips - chips
        if seat.destop_chips > self._max_bet then
            self._max_bet = seat.destop_chips
        end
    end
    self:doResp("ActionBRC", {seatid = seatid, action_type = action_type, chips = chips, hand_chips = seat.hand_chips})
end

function P:doActionNotifyBRC()
    local seat = self.room:getSeat(self.room.table_status.action_idx)
    self._actionNotify = {
        seatid = self.room.table_status.action_idx,
        call_need_chips = self._max_bet - seat.destop_chips,
        min_chipin = self._max_bet > 0 and self._max_bet * 2 or self.room.room_info.bb,
        max_chipin = seat.hand_chips,
        pre_action_result = 0,
    }
    self:doResp("ActionNotifyBRC", self._actionNotify)
    if seat.player.uid == PlayerModel:getUid() then
    else
        if 1 == self._aiIndex then
            self._aiet = 2.5
        elseif 3 == self._aiIndex then
            self._aiet = 7.5
        else
            self._aiet = 6.5
        end
    end
end

function P:doShowHandRSP(dt)
    if self._isShowHands then
        return false
    end
    self._isShowHands = true
    local infos = {}
    for _, v in ipairs(self.room.table_status.seat) do
        if v.player.uid > 0 then
            table.insert(infos, {
                seatid = v.seatid,
                card1 = v.card1,
                card2 = v.card2,
            })
        end
    end
    self:doResp("ShowHandRSP", {info = infos})
    self._stage = GAME_STAGE.Show
    self._et = dt or 1
    return true
end

function P:doWinnerRSP()
    local winners = {}
    local profits = {}
    
    local seats = self.room:getActionSeats(self.room.table_status.sb_idx)
    
    local maxCardType, maxValue, count = 0, 0, 0
    for _, v in ipairs(seats) do
        if v.action_type ~= POKER_ACTION.FOLD then
            v.retHands, _, v.cardType = PKHelper.getCardType({v.card1, v.card2}, self.room.table_status.board, self.room.game_type)
            v.cardValue = self:getCardsValue(v.retHands)
            if v.cardType > maxCardType or (v.cardType == maxCardType and v.cardValue > maxValue) then
                maxCardType = v.cardType
                maxValue = v.cardValue
                count = 1
            elseif v.cardType == maxCardType and v.cardValue == maxValue then
                count = count + 1
            end
        else
            v.retHands, v.cardValue, v.cardType = nil, 0, 0
        end
    end
    local pot = math.floor((self.room.table_status.pool[1] or 0) / count)
    for _, v in ipairs(seats) do
        if v.cardValue == maxValue and v.cardType == maxCardType then
            v.hand_chips = v.hand_chips + pot
            table.insert(winners, {
                seatid = v.seatid,
                poolid = 1,
                chips = pot,
                type = v.cardType,
                uid = v.player.uid,
                jackpot_fee = 0,
            })
        else
        end
    end
    for _, v in ipairs(seats) do
        table.insert(profits, {
            seatid = v.seatid,
            chips = v.hand_chips - v.begin_chips,
            fire_power = 0,
            win_exp = 0,
            bond_add = 0,
        })
    end

    self:doResp("WinnerRSP", {
        winner = winners,
        profit = profits,
    })
end

function P:getCardsValue(cards)
    local ret = 0
    for _, v in ipairs(cards) do
        ret = ret + v.number
    end
    return ret
end

function P:nextStage()
    if self.room.table_status.stage == POKER_ROUND.PRE_FLOP then
        self:toStage(POKER_ROUND.FLOP, GAME_STAGE.Flop, 0.8 * 3 + 1.3)
    elseif self.room.table_status.stage == POKER_ROUND.FLOP then
        self:toStage(POKER_ROUND.TURN, GAME_STAGE.Turn, 0.8 + 1.3)
    elseif self.room.table_status.stage == POKER_ROUND.TURN then
        self:toStage(POKER_ROUND.RIVER, GAME_STAGE.River, 0.8 + 1.3)
    elseif self.room.table_status.stage == POKER_ROUND.RIVER then
        self:doWinnerRSP()
    end
end

function P:toStage(stage, selfStage, et)
    self.room.table_status.stage = stage
    self:doRoundStartBRC()
    self._stage = selfStage
    self._et = et
    if stage == POKER_ROUND.RIVER then
        self._et = self._et + 2
    end
end

function P:onUpdate(dt)
    if self._et > 0 then
        self._et = self._et - dt
        if self._et <= 0 then
            if GAME_STAGE.None == self._stage then
                self:doDealerInfoRSP()
                -- self._stage = GAME_STAGE.Dealer
                -- self._et = 0.01
                self:toStage(POKER_ROUND.PRE_FLOP, GAME_STAGE.Preflop, 1.4 * 2)
            elseif GAME_STAGE.Dealer == self._stage then
                self:toStage(POKER_ROUND.PRE_FLOP, GAME_STAGE.Preflop, 1.4 * 2)
            elseif GAME_STAGE.Preflop == self._stage then
                if self:findActionIdx(self.room.table_status.sb_idx) then
                    self:doActionNotifyBRC()
                else
                    self:toStage(POKER_ROUND.FLOP, GAME_STAGE.Flop, 0.8 * 3 + 1.3)
                end
            elseif GAME_STAGE.Flop == self._stage then
                local idx = self.room.table_status.sb_idx == self.room.table_status.d_idx and self.room.table_status.bb_idx or self.room.table_status.sb_idx
                if self:findActionIdx(idx) then
                    self:doActionNotifyBRC()
                else
                    if not self:doShowHandRSP(1) then
                        self:toStage(POKER_ROUND.TURN, GAME_STAGE.Turn, 0.8 + 1.3)
                    end
                end
            elseif GAME_STAGE.Turn == self._stage then
                local idx = self.room.table_status.sb_idx == self.room.table_status.d_idx and self.room.table_status.bb_idx or self.room.table_status.sb_idx
                if self:findActionIdx(idx) then
                    self:doActionNotifyBRC()
                else
                    if not self:doShowHandRSP(1) then
                        self:toStage(POKER_ROUND.RIVER, GAME_STAGE.River, 0.8 + 1.3)
                    end
                end
            elseif GAME_STAGE.River == self._stage then
                local idx = self.room.table_status.sb_idx == self.room.table_status.d_idx and self.room.table_status.bb_idx or self.room.table_status.sb_idx
                if self:findActionIdx(idx) then
                    self:doActionNotifyBRC()
                else
                    if not self:doShowHandRSP(1) then
                        self:doWinnerRSP()
                    end
                end
            elseif GAME_STAGE.Show == self._stage then
                self:nextStage()
            elseif GAME_STAGE.Action == self._stage then
                if self:findActionIdx(self.room.table_status.action_idx + 1) then
                    self:doActionNotifyBRC()
                else
                    -- self:doRoundOverBRC()
                    self._et = 1
                    self._stage = GAME_STAGE.RoundOver
                end
            elseif GAME_STAGE.RoundOver == self._stage then
                self:doRoundOverBRC()
                self._et = 0.5
                self._stage = GAME_STAGE.NextRound
            elseif GAME_STAGE.NextRound == self._stage then
                if self:isEveryoneAllin() then
                    self:doShowHandRSP()
                else
                    self:nextStage()
                end
            end
        end
    end
    if self._aiet > 0 then
        self._aiet = self._aiet - dt
        if self._aiet <= 0 then
            local seat = self.room:getSeat(self.room.table_status.action_idx)
            if 1 == self._aiIndex then
                self:ActionREQ({
                    action_type = POKER_ACTION.RAISE,
                    chips = self._actionNotify.call_need_chips * 5,
                })
            elseif 2 == self._aiIndex then
                self:ActionREQ({
                    action_type = POKER_ACTION.CALL,
                    chips = self._actionNotify.call_need_chips,
                })
            elseif 3 == self._aiIndex then
                self:ActionREQ({
                    action_type =  POKER_ACTION.ALLIN,
                    chips = seat.hand_chips,
                })
            end
            self._aiIndex = self._aiIndex + 1

            -- if self._actionNotify.call_need_chips > 0 then
            --     if self._actionNotify.call_need_chips >= seat.hand_chips then
            --         self:ActionREQ({
            --             action_type =  POKER_ACTION.ALLIN,
            --             chips = seat.hand_chips,
            --         })
            --     else
            --         self:ActionREQ({
            --             action_type =  POKER_ACTION.CALL,
            --             chips = self._actionNotify.call_need_chips,
            --         })
            --     end
            -- else
            --     self:ActionREQ({
            --         action_type =  POKER_ACTION.CHECK,
            --         chips = 0,
            --     })
            -- end
        end
    end
end

function P:onRecv(name, data)
    local n = string.sub(name, 4)
    if self[n] then
        self[n](self, data)
        return true
    end
    return false
end

function P:doResp(name, data)
    if not bee.isRelease and "pb.HeartBeatRSP" ~= szPackType and "pb.HBPingRSP" ~= szPackType then
        print("[Net] onRecv", name, json.encode(data))
    else
    end
    net[name](net, data)
    bee.emit("evt_" .. name, data)
end

