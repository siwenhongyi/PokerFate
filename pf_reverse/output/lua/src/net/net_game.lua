net = net or {}

function net:UserLoginRSP(msg)
    LoginModel:setInQueue(false)
    PlayerModel:setIsLogin(false)
    if 0 == msg.code then
        PlayerModel:setIsLogin(true)
        LoginModel:setServerTime(msg.server_timestamp)
        ModelManager:afterLogin()
        Net:sendReq("pb.SelfUserInfoREQ", {})
        Net:sendReq("pb.UserValueREQ", {type = GPropId.Gold})
        Net:sendReq("pb.ItemListREQ", {})
        Net:sendReq("pb.RoleListREQ", {})
        Net:sendReq("pb.GetBlockChatListREQ", {})
        GachaModel:initGachaPoolList()
        FriendModel:initFriendList()
        ShopModel:initInfo()
        PlayerModel:reqCurRecord()
        -- PlayerModel:requestDecorationScheme()
        ShareModel:initShareList()
        -- EmailModel:reqEmailList(EmailModel.MAIL_TYPE.Normal, 0)
        -- EmailModel:reqEmailList(EmailModel.MAIL_TYPE.Special, 0)
        EmailModel:reqEmailList(nil, 0, function()
            EmailModel:reqEmailNum()
        end)
        TaskModel:requestTaskList()
        SignInModel:initSignData()
        NoticeModel:reqNoticeList()
        SevenDayTaskModel:initSevenTask()
        VipModel:reqVipData()
        ActivityModel:initActInfo()
        ActivityManager:reqActivityData()

        LoginModel:resetHeartBeat()
        bee.logEvent("net_delay", math.floor(Net:getDelay() * 1000), UrlManager:getServerUrl())
        local dt = math.floor(Net:getHttpDelay() * 1000)
        if dt > 0 then
            bee.logEvent("http_delay", dt, UrlManager:getHttpUrl())
        end
        UiManager:hideUI("LoginQueue")
    elseif tpl_RetCode.LOGIN_ERR_ENTER_QUEUE.code == msg.code then
        UiManager:showUI("LoginQueue", {pos = msg.pos, est_wait_time = msg.est_wait_time})
        LoginModel:resetHeartBeat()
        LoginModel:setInQueue(true)
        UiManager:hideLoadingMask("Connect")
        UiManager:hideLoadingMask("Login")
    elseif tpl_RetCode.LOGIN_ERR_QUEUE_FULL.code == msg.code then
        UiManager:showTip({
            text = _T("LAB_LOGIN_QUEUE_INFO7"),
            button = 1,
        })
        PlayerModel:setNotAutoLogin(true)
        Net:closeSocket()
        UiManager:hideLoadingMaskAll()
        bee.emit(EventDef.evt_login_fail)
    else
        PlayerModel:setNotAutoLogin(true)
        Net:closeSocket()
        UiManager:hideLoadingMaskAll()
        bee.emit(EventDef.evt_login_fail)
        if not bee.isInStart() then
            bee.enterScene("StartScene")
        end
    end
end

function net:UserLocationRSP(msg)
    GameModel.roomid = msg.roomid
    if msg.roomid and msg.roomid > 0 then
        Net:sendReq("pb.EnterRoomREQ", msg)
    elseif bee.isInGame() then
        if not GuideManager:isInGuide() then
            bee.enterScene("MainScene")
        end
    elseif bee.isInHome() then
        -- bee.enterScene("MainScene")
        bee.emit("evt_requestUpdateInfo")
    end
end

function net:UserLogoutRSP(msg)
    PlayerModel:setIsLogin(false)
    PlayerModel:setNotAutoLogin(true)
    ItemModel:clearItems()
    Net:closeSocket()
    ModelManager:afterLogout()
    if not bee.isInStart() then
        bee.enterScene("StartScene", {onEnter = function()
            if msg.code == 104 then
                UiManager:showUI("LoginNoNetwordDialog", {text = _T("LAB_REPEAT_LOGIN")})
                bee.logEvent("login-repeated")
            end
        end})
    elseif UiManager:getUI("LoginQueue") then
        UiManager:hideUI("LoginQueue")
        if msg.code == 104 then
            UiManager:showUI("LoginNoNetwordDialog", {text = _T("LAB_REPEAT_LOGIN")})
            bee.logEvent("login-repeated")
        end
    end
end

function net:ServerStopBRC(msg)
    PlayerModel:setIsLogin(false)
    PlayerModel:setNotAutoLogin(true)
    if Net:isConnected() then
        Net:closeSocket()
    end
    if not bee.isInStart() then
        bee.enterScene("StartScene", {onEnter = function()
            UiManager:showUI("LoginNoNetwordDialog", {text = _T("ERR_SERVER_STOP")})
        end})
    end
end

function net:SelfUserInfoRSP(msg)
    SettingModel:setUnlockSys(msg.unlock_modules)
    PlayerModel:setInfo(msg)
    ItemModel:setInfo(msg)
    if bee.isInStart() then
        GuideManager:setCurGuide(nil)
    end
    GuideManager:setCurStep(msg.newer_guide_step)
    VipModel:setVipLevel(msg.vip_level)
    GuideManager:getSystemGuides()

    bee.emit("evt_refreshTopInfo")
    bee.emit("evt_refreshLevel")
    bee.emit("evt_refreshName")
    bee.emit("evt_refreshAvatar")
    bee.emit("evt_refreshLobbyScene")
end

function net:SelfAchievementsRSP(msg)
    PlayerModel._achievements = msg.achievements
end

function net:UserValueRSP(msg)
    if msg.type == GPropId.Gold then
        PlayerModel:setGold(msg.value)
        if not SettingModel:isStopRefreshGold() then
            bee.emit(EventDef.evt_refreshTopInfo)
        end
    end
end

function net:ExpChangeRSP(msg)
    PlayerModel:setCurLevel(msg.level)
    PlayerModel:setExp(msg.exp)
end

function net:UnlockNewModuleRSP(msg)
    SettingModel:addUnlockSys(msg.success_ids)
end

function net:SetBlockChatRSP(msg)
    if 0 == msg.code then
        if msg.is_block then
            table.insert(PlayerModel._blockUids, {uid = msg.the_uid, block_end_time = msg.block_end_time})
        else
            for k, v in ipairs(PlayerModel._blockUids) do
                if v.uid == msg.the_uid then
                    table.remove(PlayerModel._blockUids, k)
                    break
                end
            end
        end
    end
end

function net:GetBlockChatListRSP(msg)
    PlayerModel._blockUids = msg.list
end

function net:InvitePlayBRC(msg)
    if nil == FriendModel:getBlockedInfo(msg.inviter_uid) then
        if SettingModel:isHideInvite() and GameModel.data then
            return
        end
        UiManager:showUI("FriendsRoomInvite", {data = msg})
    end
end

function net:FriendRoomWillDisbandBRC()
    UiManager:showToast(_T("LAB_FRIROOM_029"))
end

function net:FriendRoomDisbandBRC()
    bee.once(1, function()
        UiManager:showToast(_T("LAB_FRIROOM_030"))
    end)
end

function net:FriendRoomOwnerChangeBRC(msg)
    if not GameModel.data or not GameModel.data.friend_room_info then return end

    GameModel.data.friend_room_info.owner_uid = msg.owner.uid
    GameModel.data.friend_room_info.owner_name = msg.owner.name
    GameModel.data.friend_room_info.owner_avatar = msg.owner.avatar
    GameModel.data.friend_room_info.owner_frame = msg.owner.frame
end

function net:NoticeBRC(msg)
    if msg.type == tpl_PushConsts.NOTICE_CONF.code then
        NoticeModel:reqNoticeList()
    elseif msg.type == tpl_PushConsts.THEME_ACTIVITY_TASK_REFRESH.code then
        ThemeModel:reqTaskList()
    elseif msg.type == tpl_PushConsts.FESTIVAL_ACTIVITY_TASK_REFRESH.code then
        SpringFestivalModel:reqTaskList()
	elseif msg.type == tpl_PushConsts.THEME_ACTIVITY_START.code then
        if msg.message then
            local d = json.decode(msg.message)
            if d then
                ThemeModel:onActivityStart(d)
            end
        end
	elseif msg.type == tpl_PushConsts.MAIL_REFRESH.code then
        if msg.message then
            local d = json.decode(msg.message)
            if d then
                for _, v in ipairs(d) do
                    local info = EmailModel:getInfo(v)
                    EmailModel:reqEmailList(v, 0, nil, info and #info.list)
                end
            end
        end
    elseif msg.type == tpl_PushConsts.VIP_LEVEL_UP.code then    -- {old_level: 0, cur_level: 1}
        if msg.message then
            local d = json.decode(msg.message)
            if d then
                VipModel:setVipLevel(d.cur_level)
                if d.old_level ~= d.cur_level then
                    SettingModel:addVipLevelUpPop(d.old_level)
                    bee.emit(EventDef.evt_vipLevelUp, d)
                end
                VipModel:reqVipData()
            end
        end
    elseif msg.type == tpl_PushConsts.SERVER_MAINTAIN_NORMAL.code then
        if msg.message then
            local d = json.decode(msg.message)
            if d then
                GF.showServerMaintain(d)
            end
        end
    elseif msg.type == tpl_PushConsts.SERVER_MAINTAIN_AFTER_FIVE_MIN.code then
        if msg.message then
            local d = json.decode(msg.message)
            if d then
                GF.showServerMaintain(d)
            end
        end
    elseif msg.type == tpl_PushConsts.SERVER_UPDATE_PUSH.code then
        G_CHECK_FORCE_UPDATE_NEEDREDDOT = true
        if bee.isInHome() and not GuideManager:isInGuide() then
            bee.emit("evt_requestUpdateInfo")
        end
    elseif msg.type == tpl_PushConsts.STOVE_BUY_SUC.code then
        if msg.message then -- {"pid": "kkk","item_list":[{"item_id":11,"num":11,"major_type":0}]}
            local d = json.decode(msg.message)
            if d then
                ShopModel:onPaySucces(d, d)
            end
        end
    elseif msg.type >= 10091 and msg.type <= 100100 then -- pay success for stove
        if msg.message then
            local d = json.decode(msg.message)
            if d then
                ShopModel:doPaySuc()
                local pidCfg = ShopModel:getPidDataByPid(d.pid)
                ShopModel:onPaySucces(pidCfg, d)
            end
        end
	end
end

function net:HeartBeatRSP(msg)
    LoginModel:resetHeartBeat()
    if msg.server_timestamp and msg.server_timestamp > 0 then
        LoginModel:setServerTime(msg.server_timestamp)
    end
end

function net:GetServerTimeRSP(msg)
    if msg.server_timestamp and msg.server_timestamp > 0 then
        LoginModel:setServerTime(msg.server_timestamp)
    end
end

function net:SetNewerGuideStepRSP(msg)
    if msg.code == 0 then
        GuideManager:setCurStep(msg.step)
    end
end

function net:CancelLoginQueueRSP()
end

function net:LoginQueueStatusChangeBRC()
