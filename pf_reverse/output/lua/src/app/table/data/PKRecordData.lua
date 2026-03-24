-- poker 牌局回放记录
local P = class("PKRecordData")

function P:ctor(msg, title)
    self.msg = msg
    self.title = title

    self.roundIndex = 1
    self.curRound = nil -- 当前回合
    self.curIndex = nil -- 当前行动序号
    self.status = 1     -- 状态 1行动中 2showHand 3winnerRsp
    self._et = 1

    self._actions = {}  -- 行动队列{{fn, et}, ....}，用于插入不在 round action 中的动画消息
    self._stopNetUiEvent = false   -- 不发送刷新 ui 消息
end

function P:getAction()
    -- if self.curRound then
    --     return self.curRound.action[self.curIndex]
    -- end
    -- return nil
    if self.resps then
        local d = self.resps[self.respIndex]
        if d then
            return d._act
        end
    end
    return nil
end

function P:getActor()
    local act = self:getAction()
    if act then
        return self.room.table_status.seat[act.seatid + 1]
    end
    return nil
end

function P:addSeatStatus(seatid, v)
    local seat = {
        seatid = seatid,
        action_type = 0,
        player = {
            uid = v and v.uid,
            icon = v and v.icon,
            name = v and v.name,
            frame_id = v and v.frame_id,
            level = v and v.level,
            role_id = v and v.role_id,
            skin_id = v and v.skin_id,
            user_type = v and v.user_type,
        },
        hand_chips = v and v.begin_chips,
        total_chips = v and v.begin_chips,
        destop_chips = 0,
        -- has_card = v and v.uid > 0 or false,
        has_card = false,
        seat_reserve = false,
        wait_blind = false,
        reby_left_time = 0,
        card1 = 0,
        card2 = 0,
        card3 = 0,
        card4 = 0,
        hand_cards = v and v.hand_card,
    }
    return seat
end

function P:run()
    -- EnterRoomRSP
    if self.msg.seat_num == 0 then
        self.msg.seat_num = 6
    end
    local room = {
        roomid = 0,
        user_num = 6,
        game_type = self.msg.game_type,
        table_status = {
            gameid = self.msg.gameid,
            is_playing = true,
            action_idx = 0,
            d_idx = self.msg.button_seatid,
            sb_idx = (self.msg.button_seatid + 1) % 6,
            bb_idx = (self.msg.button_seatid + 2) % 6,
            seat = {},
            stage = POKER_ROUND.PRE_FLOP,
            board = {},
            tid = 0,
            is_show_card = false,
        },
        room_status = {},
        playing_status = {
            card1 = 0,
            card2 = 0,
            action_seatid = 0,
            call_need_chips = 0,
            min_chipin = 0,
            max_chipin = 0,
            action_time = 0,
            card3 = 0,
            card4 = 0,
            pre_action_type = 0,
            pre_action_chips = 0,
        },
        room_info = {
            roomid = 0,
            sb = self.msg.small_blind,
            bb = self.msg.big_blind,
            ante = 0,
            action_time = 15,
            seat_num = self.msg.seat_num or 6,
            game_type = self.msg.game_type,
            room_type = GF.isOmahaGame(self.msg.game_type) and GAME_ROOM_TYPE.OMAHA or GAME_ROOM_TYPE.HOLDEM,
        },
    }
    for _, v in ipairs(self.msg.user) do
        local seat = self:addSeatStatus(v.seatid, v)
        room.table_status.seat[v.seatid + 1] = seat
        if v.uid == PlayerModel:getUid() then
            room.playing_status.card1 = v.hand_card[1]
            room.playing_status.card2 = v.hand_card[2]
            room.playing_status.card3 = v.hand_card[3]
            room.playing_status.card4 = v.hand_card[4]
        end
    end
    for i = 1, room.room_info.seat_num do
        if not room.table_status.seat[i] then
            room.table_status.seat[i] = self:addSeatStatus(i - 1)
        end
    end
    self.room = room
    self:enterGame()
end

function P:enterGame()
    self.data = require("app.table.data.PKData"):create(self.room)
    self.data:setRecord(self)
    GameModel:setData(self.data, nil)

    bee.enterScene("GameScene", {onEnter = function()
        UiManager:showUI("PKTable3D", {data = self.data})
    end})
end

function P:isPlayOver()
    if not self.resps then
        return false
    end
    return self.respIndex >= #self.resps
end

function P:isHavePreAction()
    if not self.resps then
        return false
    end
    local act1 = self.resps[self.respIndex]
    if act1 and (act1.action_type == POKER_ACTION.SB or act1.action_type == POKER_ACTION.BB or act1.action_type == POKER_ACTION.FORCE_BB or act1.action_type == POKER_ACTION.ANTE) then
        return false
    end
    return true
end

function P:isHaveNextAction()
    if self.resps then
        return self.respIndex < #self.resps
    end
    return false
end

function P:onPreAction()
    local act1 = self.resps[self.respIndex]
    if not act1 or (act1.action_type == POKER_ACTION.SB or act1.action_type == POKER_ACTION.BB or act1.action_type == POKER_ACTION.FORCE_BB or act1.action_type == POKER_ACTION.ANTE) then
        return
    end

    if act1 and act1._lastInfo then
        local player1 = GameModel.data:getPlayer(act1.seatid + 1)
        player1:setPlayData(act1._lastInfo)
    end
    
    self.respIndex = self.respIndex - 1
    act1 = self.resps[self.respIndex]
    local round = act1._round
    if not round then
        for i = self.respIndex, 1, -1 do
            if self.resps[i]._round then
                if i - 1 > 1 then
                    self.respIndex = i - 1
                else
                    self.respIndex = i
                end
                act1 = self.resps[self.respIndex]
                round = act1._round
                break
            end
        end
        if not round then
            return
        end
    end
    if not GameModel.data:isPlaying() then
        GameModel.data:setPlaying(true)
    end

    -- self:doResp()

    GameModel.data:setRoundStage(round.stage)
    GameModel.data:setBoardInfo(round._totalBoard)
    if act1._evt == "RoundOverBRC" then
        local potInfo = {}
        for _, v in ipairs(round.pool) do
            potInfo[#potInfo + 1] = v.pot
        end
        GameModel.data:setPotInfo(potInfo)
    else
        local potInfo = {round._totalPot}
        GameModel.data:setPotInfo(potInfo)
    end

    if act1 and act1._curInfo then
        local player1 = GameModel.data:getPlayer(act1.seatid + 1)
        player1:setPlayData(act1._curInfo)
        for i = self.respIndex - 1, 1, -1 do
            if self.resps[i]._curInfo and self.resps[i].seatid ~= act1.seatid then
                player1 = GameModel.data:getPlayer(self.resps[i].seatid + 1)
                player1:setPlayData(self.resps[i]._curInfo)
            else
                break
            end
        end
    end

    local ui = UiManager:getUI("PKTable3D")
    if ui then
        ui:refreshUI()

        self:_doShowHandCard()
    end
    bee.emit(EventDef.evt_recordRunAction)
    self._et = 3
end

function P:onNextAction()
    self._stopNetUiEvent = true
    local flag = self:doNextAction()
    if flag then
        self._et = self.resps[self.respIndex]._et or 3
    end
    self._stopNetUiEvent = false
    local ui = UiManager:getUI("PKTable3D")
    if ui and flag then
        local d = self.resps[self.respIndex]
        if d and d._evt ~= "WinnerRSP" then
            ui:refreshUI()
        end
        self:_doShowHandCard()
    end
    bee.emit(EventDef.evt_recordRunAction)
end

function P:_doShowHandCard()
    local d = self.resps[self.respIndex]
    if d and d._evt == "ShowHandRSP" then
        self:emitNetUiEvent("evt_" .. d._evt, d)
    elseif d and d._evt == "WinnerRSP" then
        self:emitNetUiEvent("evt_" .. d._evt, d)
    end
end

function P:doRunAction()
    self:doResp()
end

function P:addResp(d)
    table.insert(self.resps, d)
end

function P:initResps()
    self.resps = {}

    -- 初始化所有行动顺序
    local board = {}
    local totalPot = 0
    local isAllAllin = false
    self._isAddShowHand = nil
    for k, round in ipairs(self.msg.round) do
        for _, v in ipairs(round.board) do
            table.insert(board, v)
        end
        round._totalBoard = clone(board)   -- 总公共牌，用于还原后退
        round._totalPot = totalPot
        local startRound = {
            stage = round.stage,
            board = round.board,

            _evt = "RoundStartBRC",
            _round = round,
            _et = 0.3 * #round.board + (#round.board > 0 and 1.5 or 0) + ((isAllAllin and round.stage == POKER_ROUND.RIVER) and 2 or 0),
        }
        self:addResp(startRound)

        local count, counts = 0, {}
        for _, act in ipairs(round.action) do
            local msg = {
                seatid = act.seatid,
                action_type = act.action_type,
                chips = act.action_chips,
                hand_chips = act.hand_chips,

                _act = act,
                _evt = "ActionBRC",
                _round = round,
                _et = 3,
            }
            self:addResp(msg)
            if not act.is_allin and not GF.isFoldAction(act.action_type) then
                counts[act.seatid] = 1
            else
                counts[act.seatid] = 0
            end
        end
        for _, v in pairs(counts) do
            if v == 1 then
                count = count + 1
            end
        end
        local allinFlag = isAllAllin
        if count < 2 then
            isAllAllin = true
        end

        local overRound = {
            pool = {},

            _evt = "RoundOverBRC",
            _round = round,
            _et = 0.8,
        }
        totalPot = 0
        for _, v in ipairs(round.pool) do
            overRound.pool[#overRound.pool + 1] = v.pot
            totalPot = totalPot + v.pot
        end
        self:addResp(overRound)

        if isAllAllin and isAllAllin ~= allinFlag then
            self:addShowHandRSP()
        end
    end

    self:addShowHandRSP()
    
    local d = {
        winner = {},
        profit = {},

        _evt = "WinnerRSP",
    }
    for _, v in ipairs(self.msg.winning_info) do
        d.winner[#d.winner + 1] = {
            seatid = v.seatid,
            poolid = v.poolid,
            chips = v.chips,
            type = 0,
            uid = v.uid,
        }
    end
    self:addResp(d)

    self.respIndex = 0
end

function P:addShowHandRSP()
    if self.msg.show_hand_info and #self.msg.show_hand_info > 0 and not self._isAddShowHand then
        self._isAddShowHand = true
        local d = {
            info = {},

            -- _round = {
            --     _totalBoard = clone(board),
            --     _totalPot = totalPot,
            -- },

            _evt = "ShowHandRSP",
        }
        for _, v in ipairs(self.msg.show_hand_info) do
            d.info[#d.info + 1] = {
                seatid = v.seatid,
                card1 = v.hand_card[1],
                card2 = v.hand_card[2],
                card3 = v.hand_card[3],
                card4 = v.hand_card[4],
            }
        end
        self:addResp(d)
    end
end

function P:doResp(index)
    local d = self.resps[index or self.respIndex]

    local act = d and d._act
    if act then
        if not act.hand_chips then
            local seat = self.room.table_status.seat[act.seatid + 1]
            seat.hand_chips = seat.hand_chips - act.action_chips
            act.hand_chips = seat.hand_chips

            d.hand_chips = act.hand_chips
        end
        local player = GameModel.data:getPlayer(act.seatid + 1)
        if player and not d._lastInfo then
            d._lastInfo = player:getPlayData()
        end
    end

    -- self.respIndex = (index or self.respIndex) + 1
    net[d._evt](net, d)

    if act then
        local player = GameModel.data:getPlayer(act.seatid + 1)
        if player and not d._curInfo then
            d._curInfo = player:getPlayData()
        end
    end

    self:emitNetUiEvent("evt_" .. d._evt, d)
    print("=== ggg doResp", d._evt, self._stopNetUiEvent)
    return d
end

function P:doStartAction()
    self.roundIndex = 1
    self.curRound = self.msg.round[self.roundIndex]
    self.curIndex = 1
    self.respIndex = 0
    self:initResps()

    self:doNextAction()
    while true do
        local v = self.resps[self.respIndex + 1]
        if v and v.action_type == POKER_ACTION.SB or v.action_type == POKER_ACTION.BB or v.action_type == POKER_ACTION.FORCE_BB or v.action_type == POKER_ACTION.ANTE then
            self:doNextAction()
        else
            break
        end
    end
    self._et = self._et + #self.msg.user * 0.7
    bee.emit(EventDef.evt_recordRunAction)
end

function P:doNextAction()
    if self.respIndex < #self.resps then
        self.respIndex = self.respIndex + 1
        self:doResp()
        return true
    end
    return false
end

function P:doShowHands()
    if self.msg.show_hand_info and #self.msg.show_hand_info > 0 then
        self.status = 2
        self:addAction(function()
            local d = {
                info = {}
            }
            for _, v in ipairs(self.msg.show_hand_info) do
                d.info[#d.info + 1] = {
                    seatid = v.seatid,
                    card1 = v.hand_card[1],
                    card2 = v.hand_card[2],
                    card3 = v.hand_card[3],
                    card4 = v.hand_card[4],
                }
            end
            net:ShowHandRSP(d)
            self:emitNetUiEvent("evt_ShowHandRSP", d)
        end, 1)
    end
    self:addAction(function()
        self:doWinnerRSP()
    end, 5)
end

function P:doWinnerRSP()
    self.status = 3
    local d = {
        winner = {},
        profit = {},
    }
    for _, v in ipairs(self.msg.winning_info) do
        d.winner[#d.winner + 1] = {
            seatid = v.seatid,
            poolid = v.poolid,
            chips = v.chips,
            type = 0,
            uid = v.uid,
        }
    end
    net:WinnerRSP(d)
    self:emitNetUiEvent("evt_WinnerRSP", d)
end

function P:emitNetUiEvent(name, d)
    if not self._stopNetUiEvent then
        bee.emit(name, d)
    end
end

function P:addAction(fn, et)
    if self._stopNetUiEvent then
        fn()
    else
        self._actions[#self._actions + 1] = {fn, et}
    end
end

function P:onUpdate(dt)
    if #self._actions > 0 then
        local d = self._actions[1]
        if not d["done"] then
            d["done"] = true
            d[1]()
        end
        d[2] = d[2] - dt
        if d[2] <= 0 then
            table.remove(self._actions, 1)
        end
        return
    end
    if self.curRound then
        self._et = self._et - dt
        if self._et <= 0 then
            if self:doNextAction() then
                self._et = self.resps[self.respIndex] and self.resps[self.respIndex]._et or 3
                bee.emit(EventDef.evt_recordRunAction)
            end
        end
    elseif self.status == 2 then
        -- self._et = self._et - dt
        -- if self._et <= 0 then
        --     self._et = 1
        --     self:doWinnerRSP()
        -- end
    end
end

