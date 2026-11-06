local P = class("IngameEmojiTipView", UiDialog)

function P:onAwake()
    self.EmojiIcon = self:find("Bottom/Icon")
    self.CloseButton = self:find("Bottom/CloseButton")
    -- self.ChatButton = self:find("ChatButton")

    self.freeLimitState = {
        none = 0,    
        limit = 1,
        tiped = 2,
    }

    bee.addClick(self.CloseButton, function ()
        self:onBtClose()
        bee.logEvent("ingame-emoji-close", GameModel.data:getGameType(), GameModel.data:getRoomId())
    end)
    -- bee.addClick(self.ChatButton, function ()
    --     self:onReshowChatLayer()
    -- end)

    EmojiModel:changeInteractionMode(true)
    bee.emit("evt_swtichEmojiTipView", {sw = true})
end

function P:onShow()
    if self._params == nil then
        return
    end    

    self.keepSend = self._params.keep
    self.itemId = self._params.itemId
    self.emojiId = self._params.emojiId
    self.freeLimit = self.freeLimitState.none
    self:refreshSeatInfo()
    self:showEmojiIcon()
end

function P:refreshSeatInfo()
    local index = 0
    for _,v in pairs(GameModel.layer.allSeats) do
        index = index + 1
        local playerUid = 0
        local item = self:find("Seat/Seat" .. tostring(index))

        local showable = true
        if v.transform.childCount > 0 then
            local headItem = v.transform:GetChild(0)
            local headCls = ObjectPool:getCls(headItem.gameObject)
            local info = headCls.data:getPlayer(headCls.seatid)
            playerUid = info.uid
            if playerUid == nil or playerUid == 0 or playerUid == PlayerModel:getUid() then
                showable = false
            end
        else
            showable = false
        end

        item:SetActive(showable)
        if showable then
            item.transform.localPosition = v.transform.localPosition + bee.v3(-3, 82, 0)
            bee.addClick(item, function ()
                if not bee.checkCd("SendEmojiEvent", 0.6) then
                    return
                end

                if self.freeLimit == self.freeLimitState.none and EmojiModel.freeTimes == 1 then
                    self.freeLimit = self.freeLimitState.limit
                    self:sendEmoji(playerUid)
                elseif self.freeLimit == self.freeLimitState.limit and EmojiModel.freeTimes == 0 then
                    self.freeLimit = self.freeLimitState.tiped
                    local emojiCfg = tpl_table_emoji[self.emojiId]
                    local costItemCfg = tpl_props[emojiCfg.item[1]]
                    UiManager:showTip({
                        text = _F("LAB_GAME_EMOJI_09", _T(costItemCfg.name), emojiCfg.item[2]),
                        onSure = function()
                            self:sendEmoji(playerUid)
                        end,
                        onCancel = function ()
                            self:onBtClose()
                        end
                    })
                else
                    self:sendEmoji(playerUid)
                end
            end, true)
        end
    end
end

function P:sendEmoji(playerUid)
    if EmojiModel.freeTimes <= 0 then
        local enough = EmojiModel:checkEnoughItem(self.emojiId, "LAB_GAME_EMOJI_04")
        if not enough then
            bee.logEvent("ingame-emoji-send-new", GameModel.data:getGameType(), GameModel.data:getRoomId(), playerUid, 2)
            self:onBtClose()
            return
        end
    end

    EmojiModel:SendEmoji(self.emojiId, playerUid)
end

function P:showEmojiIcon()
    local itemCfg = tpl_props[self.itemId]
    bee.setIcon(self.EmojiIcon, itemCfg.icon)
end

function P:evt_sendEmojiCallback()
    -- 上报任务进度：牌桌使用表情
    TaskModel:reportTask(TaskTargetId.TableChat, TaskTableChatType.EmojiAni)

    if not self.keepSend then
        self:onBtClose()
    end
end

function P:evt_hideUiWhenAction(isVisible)
    self:onUiBlur(not isVisible, "evt_hideUiWhenAction", true)
end

function P:evt_StandUpRSP()
    self:onBtClose()
end
function P:evt_StandUpBRC()
    self:refreshSeatInfo()
end
function P:evt_SitDownBRC()
    self:refreshSeatInfo()
end

-- function P:onReshowChatLayer()
--     self:onBtClose()
--     bee.emit("evt_reshowChatLayer")
-- end

function P:evt_clickIngameChatEvent()
    self:onBtClose()
end

function P:onBtClose()
    self:hideUI()
    -- EmojiModel:changeInteractionMode(false)
    bee.emit("evt_swtichEmojiTipView", {sw = false})
end

function P:onDestroy()
    EmojiModel:changeInteractionMode(false)
end

return P
