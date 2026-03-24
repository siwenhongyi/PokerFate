local P = class("CharacterItemsUnlocked", UiDialog)

function P:onAwake()
    self._openAnim, self._closeAnim = "UI_1_" .. self.__cname .. "_into", "UI_1_" .. self.__cname .. "_back"

    local Center = self:find("AnimRoot/Center")
    self.View1 = self:find("View1", Center)
    self.View2 = self:find("View2", Center)
    self.Item = self:find("Item", Center)
    self.Item:SetActive(false)

    self.Titles = {
        self:find("Title/Title01", Center),
        self:find("Title/Title02", Center),
        self:find("Title/Title03", Center),
    }

    bee.addClick(self:find("Mask", Center), function()
        self:hideUI()
    end)

    local lang = LanguageManager:getLanguage()
    for k, v in ipairs(Config.Languages) do
        if v == lang then
            if self.Titles[k] then
                for kk, vv in ipairs(self.Titles) do
                    vv:SetActive(kk == k)
                end
            end
            break
        end
    end
end

function P:onShow()
    self._items = self._params.items
    for k, v in ipairs(self._items) do
        if v == GPropId.CharacterEmojiId then
            table.remove(self._items, k)
            table.insert(self._items, 2, v)
        end
    end
    self:once(0.2, function()
        self:showItems()
    end)
end

function P:showItems()
    local View = #self._items > 3 and self.View2 or self.View1
    for k, v in ipairs(self._items) do
        local item = CU.GameObject.Instantiate(self.Item, View.transform, false)
        item:SetActive(true)

        local Ani_root = self:find("Ani_root", item)
        if k > 1 then
            Ani_root:SetActive(false)
            self:once((k - 1) * 0.12, function()
                Ani_root:SetActive(true)
            end)
        end
        
        local icon, ImageIcon = nil, self:find("Mask/ImageIcon", Ani_root)
        if v == GPropId.CharacterEmojiId then
            local emojis = get_tpl_subKey(tpl_emoji_list, "role", self._params.role.role_id)
            if emojis then
                for _, v in ipairs(emojis) do
                    if v.unlock == Config.AWAKEN_LEVEL + 1 then
                        icon = v.emoji
                        break
                    end
                end
            end
            bee.setIcon(self:find("Mask/ImageEmoji", Ani_root), icon or tpl_props[v].icon)
            self:find("Mask/ImageEmoji", Ani_root):SetActive(true)
            ImageIcon:SetActive(false)
        elseif tpl_props[v].type == GPropKind.Title then
            bee.setIcon(self:find("Mask/ImageTitle", Ani_root), tpl_props[v].icon)
            self:find("Mask/ImageTitle", Ani_root):SetActive(true)
            ImageIcon:SetActive(false)
        elseif tpl_props[v].type == GPropKind.Avatar then
            bee.setIcon(self:find("Mask/ImageAvatar", Ani_root), tpl_props[v].icon)
            self:find("Mask/ImageAvatar", Ani_root):SetActive(true)
            ImageIcon:SetActive(false)
        else
            bee.setIcon(ImageIcon, tpl_props[v].icon)
        end

        if v == GPropId.CharacterEmojiId or tpl_props[v].type == GPropKind.Avatar then
            bee.setText(self:find("TextName2", Ani_root), _T(tpl_props[v].name))
        else
            bee.setText(self:find("TextName1", Ani_root), _T(tpl_props[v].name))
        end
    end
end

