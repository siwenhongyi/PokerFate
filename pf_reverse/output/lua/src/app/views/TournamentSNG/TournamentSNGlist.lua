local P = class("TournamentSNGlist", UiDialog)

function P:onAwake()
    self.Panel = self:find("AnimRoot/Center/Panel")

    self.Items = {
        self:find("Item1", self.Panel),
        self:find("Item2", self.Panel),
        self:find("Item3", self.Panel),
    }

    bee.addClick(self:find("CloseButton", self.Panel), function()
        self:hideUI()
    end)
end

function P:onShow()
    if self._params and self._params.data then
        for k, v in ipairs(self._params.data) do
            if v.reward_item_list and #v.reward_item_list > 0 then
                local Reward = self:find("Reward", self.Items[k])
                Reward:SetActive(true)
                local Item01 = self:find("Reward/Item01", self.Items[k])
                for kk, vv in ipairs(v.reward_item_list) do
                    local item = CU.GameObject.Instantiate(Item01, Reward.transform, false)
                    bee.setText(self:find("TextCount", item), _N(vv.item_num))
                    bee.setIcon(self:find("Icon", item), tpl_props[vv.item_id].icon)
                    item:SetActive(true)

                    bee.addClick(item, function()
                        UiManager:showUI("CommonItemTip", {data = vv, target = self:find("Icon", item)})
                    end)
                end
                if self._params.champion_points and self._params.champion_points > 0 then
                    bee.setText(self:find("TextCount", Item01), _N(self._params.champion_points))
                    bee.setIcon(self:find("Icon", Item01), tpl_props[GPropId.ChampionPoints].icon)
                    Item01:SetActive(true)
                    bee.addClick(Item01, function()
                        UiManager:showUI("CommonItemTip", {data = {item_id = GPropId.ChampionPoints}, target = self:find("Icon", Item01)})
                    end)
                else
                    Item01:SetActive(false)
                end
                self:find("tournament_sng_rewards_line", self.Items[k]):SetActive(false)
            else
                self:find("tournament_sng_rewards_line", self.Items[k]):SetActive(true)
                self:find("Reward", self.Items[k]):SetActive(false)
            end
            GF.setFrameImage(self:find("Avatar/ImageFrame", self.Items[k]), v.brief.frame)
            GF.setTitleImage(self:find("ImageTitle", self.Items[k]), v.brief.title)
            bee.setText(self:find("TextName", self.Items[k]), v.brief.name)
            bee.setIcon(self:find("Avatar/Mask/Icon", self.Items[k]), PlayerModel:getAvatarIcon(v.brief.avatar))
            
            bee.addClick(self:find("Avatar", self.Items[k]), function()
                Game:playSound("ui_button_confirm")
                if v.brief.uid == PlayerModel:getUid() then
                    UiManager:showUI("InformationMainNew", {from = "Ranking"})
                else
                    UiManager:showUI("InformationMainNew", {uid = v.brief.uid, from = "Ranking"})
                end
            end)
        end
    end
end

return P