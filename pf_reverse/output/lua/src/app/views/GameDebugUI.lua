local P = class("GameDebugUI", UiBase)

function P:ctor(params)
    P.super.ctor(self, params)
end

function P:onAwake()
    local BgDebug = self:find("BgDebug")
    if bee.isRelease and not bee.isEditor then
        for i = 0, BgDebug.transform.childCount - 1 do
            local child = BgDebug.transform:GetChild(i)
            child.gameObject:SetActive("BtReport" == child.gameObject.name)
        end
    end
    if PlayerModel then
        PlayerModel:setUsedGm(true)
    end
    self.data = GameModel.data
    self.inPop = true
    self:on("init", function(e)
        self.layer = e
    end)
    if Game and Game.logic then
        self.layer = Game.logic._layer
    end
end

function P:onShow()
    if bee.isEditor then
        for k, v in pairs(package.loaded) do
            if string.find(k, "app.views.") then
                package.loaded[k] = nil
            end
        end
    end
end

function P:onBtTestCommonTip()
    bee.showUiTask("LevelUpgrade")
    bee.showUiTask("LevelUnlock", {ids = {201}})
    bee.runTask()
end

function P:onBtRefreshGame()
    if GameModel.data then
		GameModel:reqGetRoomDataREQ()
    end
end

function P:onBtKaiSvr()
    if G_SERVER_URL ~= "ws://10.100.5.56:9012" then
        G_SERVER_URL = "ws://10.100.5.56:9012"
        if PlayerModel:isLogin() then
			Net:sendReq("pb.UserLogoutREQ", {})
        end
    end
end

function P:onBtHaiSvr()
    if G_SERVER_URL ~= "ws://10.100.5.62:9012" then
        G_SERVER_URL = "ws://10.100.5.62:9012"
        if PlayerModel:isLogin() then
			Net:sendReq("pb.UserLogoutREQ", {})
        end
    end
end

function P:onBtCheckEN()
    for _, v in ipairs(tpl_mult_language_list) do
        if v.en and v.id ~= "LAB_LAN_JP" and v.id ~= "LAB_LAN_EN" and v.id ~= "LAB_LAN_TW" and v.id ~= "LAB_LAN_KO" then
            local s = v.en
            
            local i = 1
            while i <= #s do
                if string.byte(s, i) > 127 then
                    if string.byte(s, i) == 226 and i + 2 <= #s and string.byte(s, i + 1) == 128 and (string.byte(s, i + 2) == 148 or string.byte(s, i + 2) == 147) then
                        -- 处理特殊的长短破折号
                        i = i + 3
                    else
                        printError("发现英文非 ASCII 字符：" .. v.id .. " " .. string.sub(v.en, i))
                        break
                    end
                end
                i = i + 1
            end
        end
    end
end

function P:testWinOdds()
    local nums = {"1", "2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"}
    local suits = {"c", "d", "h", "s"}
    local hands = {
        {{GF.getCardCode(14, 1), GF.getCardCode(14, 2)}, {GF.getCardCode(13, 1), GF.getCardCode(13, 2)}},
        {{GF.getCardCode(14, 1), GF.getCardCode(14, 2)}, {GF.getCardCode(14, 3), GF.getCardCode(13, 2)}},
    }
    for k, v in ipairs(hands) do
        CS.WinOdds.CalculateWinOdds(string.format("1,%d,%d;2,%d,%d", v[1][1], v[1][2], v[2][1], v[2][2]), "", "", os.time(), 3000, function(result)
            local d = json.decode(result)
            print("==== 计算胜率结果", 
            nums[GF.getCardNumber(v[1][1])] .. suits[GF.getCardSuit(v[1][1])] .. nums[GF.getCardNumber(v[1][2])] .. suits[GF.getCardSuit(v[1][2])] .. " : " ..
            nums[GF.getCardNumber(v[2][1])] .. suits[GF.getCardSuit(v[2][1])] .. nums[GF.getCardNumber(v[2][2])] .. suits[GF.getCardSuit(v[2][2])], 
            d[1][1] .. ":" .. d[1][2], d[2][1] .. ":" .. d[2][2])
        end)
    end
end

function P:testWheelAnim()
    UiManager:showUI("GachaWheelMask")
    -- local wheel = bee.createObj("views/Gacha/GachaWheelAnim")
    -- wheel.transform:SetParent(bee.find("UIRoot").transform, false)
end

function P:testIngameBondsUp()
    UiManager:showUI("IngameBondsUp", {info = {
        role_id = PlayerModel:getUid(),
        bond_inc = 0,
        cur_bond_level = 3,
        old_bond_level = 2,
        win_hands = 1,
    }}, nil, LOBBY_POP_PRIORITY.BondUp)
end

function P:onBtClaimResult()

    -- self:showGameResult()
    -- do return end
    local _getItem = function()
        local ids = {10615007, 10602003, 10603002, 10604006}
        local item = clone(ItemModel:getItem(ids[math.random(#ids)], true))
        item.is_decompose = true
        item.decompose_item = ItemModel:getItem(10602004, true)
        return item
    end
    UiManager:showUI("BackpackClaimResult", {
        items = {
            _getItem(),
            _getItem(),
            _getItem(),
            _getItem(),
            _getItem(),
            _getItem(),
            _getItem(),
            _getItem(),
            _getItem(),
            _getItem(),
            _getItem(),
            _getItem(),
            _getItem(),
            _getItem(),
            _getItem(),
            _getItem(),
            _getItem(),
            _getItem(),
        }
    })
end

function P:onBtReport()
    local Reporter = bee.find("Reporter")
    if Reporter then
        Reporter:BroadcastMessage("doShow")
    end
    self:hideUI()
end

function P:showGameResult()
    UiManager:hideUI("IngameResult")
    local k = 10
    local c = 4
    local boards, hand_cards = nil, nil
    if 1 == k then
        boards = {GF.getCardCode(9,1),GF.getCardCode(10,2),GF.getCardCode(7,3)}
        hand_cards = {GF.getCardCode(6,3),GF.getCardCode(14,4)}
    elseif 2 == k then
        boards = {GF.getCardCode(10,1),GF.getCardCode(10,2),GF.getCardCode(7,3)}
        hand_cards = {GF.getCardCode(6,3),GF.getCardCode(14,4)}
    elseif 3 == k then
        boards = {GF.getCardCode(10,1),GF.getCardCode(10,2),GF.getCardCode(7,3)}
        hand_cards = {GF.getCardCode(7,3),GF.getCardCode(14,4)}
    elseif 4 == k then
        boards = {GF.getCardCode(10,1),GF.getCardCode(10,2),GF.getCardCode(10,3)}
        hand_cards = {GF.getCardCode(6,3),GF.getCardCode(14,4)}
    elseif 5 == k then
        boards = {GF.getCardCode(10,1),GF.getCardCode(9,2),GF.getCardCode(7,3)}
        hand_cards = {GF.getCardCode(8,3),GF.getCardCode(6,4)}
    elseif 6 == k then
        boards = {GF.getCardCode(10,1),GF.getCardCode(9,1),GF.getCardCode(7,1)}
        hand_cards = {GF.getCardCode(6,1),GF.getCardCode(14,1)}
    elseif 7 == k then
        boards = {GF.getCardCode(10,1),GF.getCardCode(10,2),GF.getCardCode(10,3)}
        hand_cards = {GF.getCardCode(14,2),GF.getCardCode(14,1)}
    elseif 8 == k then
        boards = {GF.getCardCode(10,1),GF.getCardCode(10,2),GF.getCardCode(10,3)}
        hand_cards = {GF.getCardCode(10,4),GF.getCardCode(14,1)}
    elseif 9 == k then
        boards = {GF.getCardCode(10,c),GF.getCardCode(9,c),GF.getCardCode(7,c)}
        hand_cards = {GF.getCardCode(6,c),GF.getCardCode(8,c)}
    elseif 10 == k then
        boards = {GF.getCardCode(10,c),GF.getCardCode(11,c),GF.getCardCode(12,c)}
        hand_cards = {GF.getCardCode(13,c),GF.getCardCode(14,c)}
    end
    UiManager:showUI("IngameResult", {
        boards = boards,
        hand_cards = hand_cards,
        player = {name="test", level = 1}, 
        seatid = 1, chips = 0, msg = {}
    })
end

function P:checkCardType()
    -- local c, t = PKHelper.getOmahaType({514,1031,519,259}, {263,261,526,1036,1026})
    -- print("==== gggggg", json.encode(c), _T(t))
    -- c, t = PKHelper.getOmahaType({GF.getCardCode(2,1),GF.getCardCode(3,2),GF.getCardCode(4,3),GF.getCardCode(7,4)}, 
    -- {GF.getCardCode(8,1),GF.getCardCode(9,1),GF.getCardCode(10,1),GF.getCardCode(11,1),GF.getCardCode(12,1)})
    -- print("==== gggggg", json.encode(c), _T(t))

    c, t = PKHelper.getOmahaType({GF.getCardCode(10,1),GF.getCardCode(10,2),GF.getCardCode(7,3),GF.getCardCode(14,4)}, 
    {GF.getCardCode(2,1),GF.getCardCode(9,1),GF.getCardCode(7,1)})
    print("==== gggggg", json.encode(c), _T(t))

    c, t = PKHelper.getOmahaType({GF.getCardCode(6,1),GF.getCardCode(6,2),GF.getCardCode(7,3),GF.getCardCode(14,4)}, 
    {GF.getCardCode(2,1),GF.getCardCode(9,1),GF.getCardCode(7,1)})
    print("==== gggggg", json.encode(c), _T(t))

    c, t = PKHelper.getOmahaType({GF.getCardCode(5,1),GF.getCardCode(3,2),GF.getCardCode(4,3),GF.getCardCode(13,4)}, 
    {GF.getCardCode(2,1),GF.getCardCode(2,2),GF.getCardCode(4,2),GF.getCardCode(3,4),GF.getCardCode(8,1)})
    print("==== gggggg", json.encode(c), _T(t))

    c, t = PKHelper.getOmahaType({GF.getCardCode(4,1),GF.getCardCode(3,2),GF.getCardCode(14,3),GF.getCardCode(13,4)}, 
    {GF.getCardCode(2,1),GF.getCardCode(2,2),GF.getCardCode(2,2),GF.getCardCode(3,4),GF.getCardCode(3,1)})
    print("==== gggggg", json.encode(c), _T(t))

    c, t = PKHelper.getOmahaType({GF.getCardCode(2,1),GF.getCardCode(3,2),GF.getCardCode(14,3),GF.getCardCode(3,4)}, 
    {GF.getCardCode(2,1),GF.getCardCode(2,2),GF.getCardCode(6,2),GF.getCardCode(14,4),GF.getCardCode(3,1)})
    print("==== gggggg", json.encode(c), _T(t))

    c, t = PKHelper.getOmahaType({GF.getCardCode(2,4),GF.getCardCode(3,4),GF.getCardCode(14,1),GF.getCardCode(6,2)}, 
    {GF.getCardCode(5,3),GF.getCardCode(7,2),GF.getCardCode(14,4),GF.getCardCode(4,3),GF.getCardCode(2,1)})
    print("==== gggggg", json.encode(c), _T(t))

    c, t = PKHelper.getOmahaType({GF.getCardCode(12,4),GF.getCardCode(12,3),GF.getCardCode(9,1),GF.getCardCode(10,2)}, 
    {GF.getCardCode(5,3),GF.getCardCode(5,2),GF.getCardCode(14,4),GF.getCardCode(9,3),GF.getCardCode(10,1)})
    print("==== gggggg", json.encode(c), _T(t))
end

function P:showBookCollection()
    local ui = UiManager:getUI("MainUI")
    if not ui then return end
    
    local params = {}
    params.collectionCount = 20                 -- 本次收集的次数
    params.oldCollectedNum = 10     -- 旧的收集进度
    params.curCollectedNum = 100            -- 新的收集进度
    params.collectionScale = 2
    params.collectionDouble = nil
    params.curReward = {collectedNum = 20, collection = 20, id = 2, count = 1}                      -- 目前奖励进度
    -- params.newRewardList = {{id = 2, count = 1, collection = 20, totalCollection = 20}}              -- 本次获得的奖励列表
    params.newRewardList = {{id = 2, count = 1, collection = 20, totalCollection = 20},{id = 3, count = 1, collection = 100, totalCollection = 100} }               -- 本次获得的奖励列表
    params.nextReward = {id = 2, count = 1, collection = 100, totalCollection = 200}                        -- 下一个未领取的奖励
    params.isShowGetAnim = true
    params.actId = ActivityID.ItemsCollection
    params.item = ui.cls._activeUIRoot._activeTop
    UiManager:showUI("views/MainDialog/ActivityGatherAnimDialog", params)
end

function P:onBtPrint()
    -- for k, v in pairs(UiManager._uiList) do
    --     print("============ ggg", k, v.node, v.cls, v.cls.__from, v.cls.__cname)
    -- end

    -- for k, v in pairs(bee._evts) do
    --     for _, vv in ipairs(v) do
    --         if vv[2] then
    --             print("==== ggg", k, vv[1], vv[2], vv[2].__cname, vv[2].node, bee.isNull(vv[2].node), vv[2]._eventListeners, vv[2].__from)
    --         else
    --             print("====== ggg", k, vv[1], vv[2])
    --         end
    --     end
    -- end

    if bee._tasks then
        for _, v in pairs(bee._tasks) do
            if #v > 0 then
                print("====== 任务队列数量：", #v, v[1].status, v[1].__cname)
            end
        end
    end

    for _, v in pairs(UiManager:getUiStack()) do
        print("==== gggg", v.cls.uiName)
    end

    local info, lvl, ver = GameSaveInfo2:getGameDropInfo(PlayerModel:getCurLevel())
    print("====== 掉落 等级:", Game.logic and Game.logic._dropRateLvl or lvl, "基础等级:", GameSaveInfo2:getTechLvl(), "连胜:", GameSaveInfo2._data.win, "连败:", GameSaveInfo2._data.lose)
    GameSaveInfo2:getTechScore(true)
    print("====== 掉落", json.encode(GameSaveInfo2._data))
    if Game.logic then
        print("====== 掉落 掉落表:", json.encode(Game.logic._dropLogic.dropRateInfo), "变难:", Game.logic._dropLogic.dropRateDiff, "剩余数量:", Game.logic._dropLogic.dropRateCount)
    end

    if not self.layer then return end
    self.layer._logic:printState()
    self.layer._logic._dropLogic.isStop = false

    print("====== 掉落 当前关卡", self.layer._logic._jsonId)
end

function P:onBtEdit()
    if not self.layer then
        UiManager:showUIatEditor("EditLevelLayer")
        self:hideUI()
        return
    end
    if self.layer._guide then
        self.layer._guide:doClose()
        self.layer._guide = nil
    end
    if self.layer._inTest then
        bee.emit("re_edit_level")
    else
        UiManager:showUIatEditor("EditLevelLayer")
    end
    self.layer.node:SetActive(false)
    self:hideUI()
end

function P:onBtRestart()
    if self.layer._inTest then
        bee.emit("try_play_level", self.layer._testData)
    else
        self.layer:_doRestart(self.layer._logic._jsonId or self.layer._logic._levelId)
    end
end

function P:onBtFast()
    if CU.Time.timeScale > 1 then
        CU.Time.timeScale = 1
    else
        CU.Time.timeScale = 3
    end
end

function P:onBtSlow()
    if CU.Time.timeScale < 1 then
        CU.Time.timeScale = 1
    else
        CU.Time.timeScale = 0.1
    end
end


function P:onBtGmDialog(obj)
    UiManager:showUI("views/GMDialog")
end

function P:onBtAiTest()
    self.node:SetActive(false)

    UiManager:showUIatEditor("Assets/editor_level/EditAiTest")
    do return end

    print("开始对关卡进行 AI 测试")
    
    LogTool:setPause(true)
    local tag = nil
    local i, aiTest = 0, nil
    local ais = {}
    tag = scheduler:schedule(0, function()
        if not aiTest or aiTest:isOver() then
            i = i + 1
            if i <= 100 then
                print("start ai test", i)
                aiTest = require("app.ai.GameAiTest"):create()
                local logic = require("app.game.GameLogic"):create(true)
                logic:initWithLevel(Game:getLevelId())
                logic:setLayer(require("app.ai.GameAiLayer"))
                logic:onGameStart(nil)
                logic._dropLogic.isTest = nil
                aiTest:startAutoTest(logic)
                ais[#ais+1] = aiTest
            else
                scheduler:removeTag(tag)
                LogTool:setPause(false)
                print("Ai 测试结束：")
                local sum, win, addMoveNum = 0, 0, 0
                local totalMove, curMove = 0, 0
                for k, v in ipairs(ais) do
                    sum = sum + 1
                    if v.logic:isWin() then
                        win = win + 1
                    else
                    end
                    if 1 == v.logic._moveState then
                        addMoveNum = addMoveNum + 1
                    end
                    totalMove = totalMove + v.logic._totalMove
                    curMove = curMove + v.logic._curMove
                end
                print("总次数：" .. sum .. "，胜利：" .. win .. "，增加步数次数：" .. addMoveNum)
                print("总步数：" .. ais[1].logic._totalMove .. "，平均使用：" .. curMove / sum)
            end
        end
    end)

    -- for i = 1, 1000 do
    --     local aiTest = require("app.ai.GameAiTest"):create()
    --     local logic = require("app.game.GameLogic"):create(true)
    --     logic:initWithLevel(Game:getLevelId())
    --     logic:setLayer(aiTest)
    --     aiTest:startAutoTest(logic)
    -- end
end

function P:onBtSaveGame()
    local logic = Game.logic
    
    Game:saveGameback(logic, true)
end

function P:onBtLoadGame()
    local path = CS.FileUtils.GetWritePath() .. "gamedata/"
    local name = CS.FileUtils.GetSelectFilePath("选择数据", path, "txt")
    if name and "" ~= name then
        local s = CS.FileUtils.ReadAllBytesSafely(name)
        
        local data = require("app.playback.GameDataOp"):create(s)
        data:run()
    end
end

function P:onGCTest()
    ResManager:UnloadUnusedAssets()
    bee.gc()
end

function P:onBtStory()
    self:hideUI()
    require('Assets.editor_story.src.EditStoryUtils')
    editor_refreshRoleIds()
    UiManager:showUIatEditor("Assets/editor_story/EditStoryLayer")
end

function P:onBtTestList()
    if self._list then
        
        local datas = {}
        datas[1] = {
            val = 1,
            __kind = 1,
        }
        for i = 2, 3 do
            datas[i] = {
                val = i,
                __kind = 2,
            }
        end
        self._list:append(datas)
        self._list:moveToYItem(#self._list._items)
        return
    end
    local obj = self:find("BgDebug/Scroll View")
    local item1 = self:find("Item1", obj)
    local item2 = self:find("Item2", obj)
    obj:SetActive(true)
    local list = require("ui.UiListEx"):create(obj)
    self._list = list
    list:setCreateFunc(function(data)
        if 1 == data.__kind then
            return CU.GameObject.Instantiate(item1)
        else
            local item = CU.GameObject.Instantiate(item2)
            bee.addClick(item, function()
                local data = list:removeItem(item, 0.5, true)
                list:moveToYItem(1, 2)
                local parent = item.transform.parent
                item.transform:SetParent(obj.transform)
                bee.tween(item)
                : to(2.5, {position = bee.v3(0, 395)})
                : onComplete(function()
                    item.transform:SetParent(parent)
                    list:insertItem(1, data, 0.5, item)
                end)
            end, true)
            return item
        end
    end)
    list:setRefreshFunc(function(data, item)
        bee.setText(bee.find("Text", item), "列表 " .. tostring(data.val))
    end)
    local datas = {}
    datas[1] = {
        val = 1,
        __kind = 2,
    }
    for i = 2, 100 do
        datas[i] = {
            val = i,
            __kind = 2,
        }
    end

    list:setWidth({
        [1] = 200,
        [2] = 100,
    })
    list:setSpacing(10)
    list:setTopBottom(20, 20)
    list:setDatas(datas)
end

function P:hideUI()
    P.super.hideUI(self)
    local ui = UiManager:getUI("GMDialog")
    if ui and ui.cls then
        ui.cls:hideUI()
    end
end

function P:onBtRoleSmall(obj, face)
    local ui = UiManager:getUI("CharacterRoleCanvas")
    if ui then
        ui:invokeSpine("playAnim", nil, nil, face)
        return
    end
    local ui = UiManager:getUI("LobbyLayer")
    if ui then
        ui.characterCls:playAnim(nil, nil, face)
    end
end

return P