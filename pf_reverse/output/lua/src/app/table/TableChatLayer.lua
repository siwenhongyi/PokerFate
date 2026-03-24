local P = class("TableChatLayer", UiDialog)

function P:onAwake()
    local Right = self:find("Right")
    local ChatTab = self:find("ChatTab", Right)
    self.EmojiToggle = self:find("EmojiToggle", ChatTab)
    self.FastToggle = self:find("FastToggle", ChatTab)
    self.ChatFoldButton = self:find("ChatFoldButton", Right)

    self.EmojiList = self:find("EmojiList", Right)
    self.FastList = self:find("FastList", Right)
    self.ItemEmoji = self:find("Item1", self.EmojiList)
    self.ItemChat = self:find("Item1", self.FastList)

    self.ItemEmoji:SetActive(false)
    self.ItemChat:SetActive(false)

    bee.addClick(self.ChatFoldButton, function()
        self:hideUI()
    end)

    bee.addValueChanged(self.EmojiToggle, function(isOn)
        if isOn then
            Game:playSound("ui_tab_switch_1")
            self:showEmoji()
            LocalStore:setIntegerForKey("table_chat_index", 0)
        end
    end)

    bee.addValueChanged(self.FastToggle, function(isOn)
        if isOn then
            Game:playSound("ui_tab_switch_1")
            self:showChat()
            LocalStore:setIntegerForKey("table_chat_index", 1)
        end
    end)
end

function P:onShow()
    if 0 == LocalStore:getIntegerForKey("table_chat_index", 0) then
        bee.setCheck(self.EmojiToggle)
        self:showEmoji()
    else
        bee.setCheck(self.FastToggle)
        self:showChat()
    end
end

function P:showEmoji()
    self.EmojiList:SetActive(true)
    self.FastList:SetActive(false)

    if not self.ListEmoji then
        self.ListEmoji = self:find("Viewport/Content", self.EmojiList)

        local emojis = get_tpl_subKey(tpl_emoji_list, "role", CharacterModel:getUsingRoleId())
        local datas, r = {}, CharacterModel:getCurRole()
        for k, v in ipairs(emojis) do
            if not r or (v.unlock and r:getBondLevel() >= v.unlock) then
                table.insert(datas, v)
            end
        end
        
        for _, data in ipairs(datas) do
            local item = CU.GameObject.Instantiate(self.ItemEmoji, self.ListEmoji.transform, false)
            item:SetActive(true)
            bee.setIcon(self:find("ingame_chat_emoji_01", item), data.emoji)
            bee.addClick(item, function()
                if not self:checkChatCD() then
                    return
                end
                Game:playSound("ui_button_confirm")
                Net:sendReq("pb.FaceREQ", {id = data.id})
                -- 上报任务进度：牌桌使用表情
                TaskModel:reportTask(TaskTargetId.TableChat, TaskTableChatType.Emoji)
                bee.logEvent("ingame-chat-emoji", GameModel.data:getGameType(), GameModel.data:getRoomId(), data.id)
                self:hideUI(nil, true)
            end, true)
        end
    end
end

function P:showChat()
    self.EmojiList:SetActive(false)
    self.FastList:SetActive(true)

    if not self.ListChat then
        self.ListChat = self:find("Viewport/Content", self.FastList)

        local chats = get_tpl_subKey(tpl_chat_list, "role", CharacterModel:getUsingRoleId())
        local datas, r = {}, CharacterModel:getCurRole()
        for k, v in ipairs(chats) do
            if v.kind == CHAT_VOICE_TYPE.Chat and (not r or r:getBondLevel() >= v.unlock) then
                table.insert(datas, v)
            end
        end
        
        for _, data in ipairs(datas) do
            local item = CU.GameObject.Instantiate(self.ItemChat, self.ListChat.transform, false)
            item:SetActive(true)
            bee.setText(self:find("Text", item), _T(data.text))
            bee.addClick(item, function()
                if not self:checkChatCD() then
                    return
                end
                Net:sendReq("pb.TextREQ", {id = data.id})
                -- 上报任务进度：牌桌使用快捷语
                TaskModel:reportTask(TaskTargetId.TableChat, TaskTableChatType.Text)
                bee.logEvent("ingame-chat-message", GameModel.data:getGameType(), GameModel.data:getRoomId(), data.id)
                self:hideUI(nil, true)
            end, true)
        end
    end
end

local _table_chat_cd = 0
function P:checkChatCD()
    local ct = bee.getServerTime()
    if math.abs(ct - _table_chat_cd) <= tpl_constdata.Quick_Chat_Cd_Time then
        local dt = math.ceil(math.abs(tpl_constdata.Quick_Chat_Cd_Time - math.abs(ct - _table_chat_cd)))
        if dt <= 0 then dt = 1 end
        UiManager:showToast(_F("LAB_GAME_007", dt))
        return false
    end
    _table_chat_cd = ct
    return true
end

function P:onPointerClick(e)
    self:hideUI()
end

function P:evt_hideUiWhenAction(isVisible)
    self:onUiBlur(not isVisible, "evt_hideUiWhenAction", true)
end

function P:evt_gameBlur(flag, name)
    self:evt_uiBlur(flag, name)
end

