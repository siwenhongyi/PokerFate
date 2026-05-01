net = net or {}

function net:ItemListRSP(msg)
    ItemModel:setItems(msg.item_list)
    ItemModel:setOwnedItems(msg.owned_item_id_list)
end

function net:ItemChangeRSP(msg)
    ItemModel:refreshItems(msg.item_list)
    local flag = false
    for _, v in ipairs(msg.item_list) do
        if not flag and v.num >= 0 and tpl_props[v.item_id] and tpl_props[v.item_id].type <= GPropKind.TicketRole then
            flag = true
        end
    end
    ItemModel:refreshReddot()

    if flag and not SettingModel:isStopRefreshGold() then
        bee.emit(EventDef.evt_refreshTopInfo)
    end
end

function net:UseItemRSP(msg)
end

function net:RecyleItemRSP(msg)
    bee.emit("evt_RecycleItemRSP", msg.reward_list)
end

function net:ChangeAvatarRSP(msg)
    if 0 == msg.code then
        PlayerModel._avatarOld = PlayerModel._avatar
        PlayerModel._avatar = msg.item_id
    end
end

function net:ChangeFrameRSP(msg)
    if 0 == msg.code then
        PlayerModel._frameOld = PlayerModel._frame
        PlayerModel._frame = msg.item_id
    end
end

function net:ChangeTitleRSP(msg)
    if 0 == msg.code then
        PlayerModel._titleOld = PlayerModel._title
        PlayerModel._title = msg.item_id
    end
end

function net:ChangeOutFitsRSP(msg)
    if 0 == msg.code then
        ItemModel:setOutFits(msg)
    end
end

function net:ChangeAnimationRSP(msg)
    if 0 == msg.code then
        PlayerModel:setAnimationInfo(msg)
    end
end