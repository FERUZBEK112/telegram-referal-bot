import "dotenv/config";
import crypto from "node:crypto";
import path from "node:path";
import { fileURLToPath } from "node:url";
import express from "express";
import helmet from "helmet";
import pg from "pg";
import { Telegraf, Markup } from "telegraf";

const env=process.env;
const required=["BOT_TOKEN","DATABASE_URL"];
for(const k of required) if(!env[k]) throw new Error(k+" is required");
const BOT_TOKEN=env.BOT_TOKEN;
const PUBLIC_URL=(env.PUBLIC_URL||"").replace(/\/$/,"");
const SUPPORT=(env.SUPPORT_USERNAME||"mrjvxrv").replace("@","");
const CARD_NUMBER=env.CARD_NUMBER||"Karta raqami hali kiritilmagan";
const CARD_HOLDER=env.CARD_HOLDER||"";
const REF_REWARD=Number(env.REFERRAL_REWARD||0.5);
const PRICES={star:Number(env.STAR_PRICE_UZS||220),premium3:Number(env.PREMIUM_3_UZS||150000),premium6:Number(env.PREMIUM_6_UZS||230000),premium12:Number(env.PREMIUM_12_UZS||370000),giftBear:Number(env.GIFT_BEAR_UZS||5000),giftRose:Number(env.GIFT_ROSE_UZS||8000),giftRocket:Number(env.GIFT_ROCKET_UZS||10000),giftDiamond:Number(env.GIFT_DIAMOND_UZS||15000),nftBase:Number(env.NFT_BASE_UZS||350000)};
const ROOT_ADMINS=(env.ADMIN_IDS||"7538161787").split(",").map(Number).filter(Boolean);
const pool=new pg.Pool({connectionString:env.DATABASE_URL,ssl:env.PGSSL==="true"?{rejectUnauthorized:false}:undefined});
const bot=new Telegraf(BOT_TOKEN);
const WEBHOOK_SECRET=crypto.createHash("sha256").update(BOT_TOKEN).digest("hex");
const app=express();
const __dirname=path.dirname(fileURLToPath(import.meta.url));
app.use(helmet({contentSecurityPolicy:false,crossOriginEmbedderPolicy:false}));
app.use(express.json({limit:"200kb"}));
app.use(express.static(path.join(__dirname,"public"),{maxAge:0,etag:true}));

async function dbInit(){
 await pool.query(`
 CREATE TABLE IF NOT EXISTS users(telegram_id BIGINT PRIMARY KEY,first_name TEXT NOT NULL,username TEXT,language TEXT NOT NULL DEFAULT 'uz',theme TEXT NOT NULL DEFAULT 'system',balance NUMERIC(12,2) NOT NULL DEFAULT 0,referred_by BIGINT,created_at TIMESTAMPTZ DEFAULT NOW(),last_seen TIMESTAMPTZ DEFAULT NOW());
 CREATE TABLE IF NOT EXISTS referrals(id BIGSERIAL PRIMARY KEY,referrer_id BIGINT NOT NULL,referred_id BIGINT UNIQUE NOT NULL,reward NUMERIC(12,2) NOT NULL,created_at TIMESTAMPTZ DEFAULT NOW());
 CREATE TABLE IF NOT EXISTS admins(telegram_id BIGINT PRIMARY KEY,added_by BIGINT,created_at TIMESTAMPTZ DEFAULT NOW());
 CREATE TABLE IF NOT EXISTS orders(id BIGSERIAL PRIMARY KEY,telegram_id BIGINT NOT NULL,product_type TEXT NOT NULL,product_name TEXT NOT NULL,quantity NUMERIC(12,2) NOT NULL,price NUMERIC(14,2) NOT NULL,recipient TEXT,status TEXT NOT NULL DEFAULT 'new',note TEXT,created_at TIMESTAMPTZ DEFAULT NOW(),updated_at TIMESTAMPTZ DEFAULT NOW());
 CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(telegram_id,created_at DESC);
 CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status,created_at DESC);
 `);
 for(const id of ROOT_ADMINS) await pool.query("INSERT INTO admins(telegram_id,added_by) VALUES($1,$1) ON CONFLICT DO NOTHING",[id]);
}
function validInit(raw){
 try{
  if(!raw) return null; const p=new URLSearchParams(raw),hash=p.get("hash"); if(!hash)return null;p.delete("hash");
  const auth=Number(p.get("auth_date")||0); if(!auth||Date.now()/1000-auth>86400)return null;
  const check=[...p.entries()].sort(([a],[b])=>a.localeCompare(b)).map(([k,v])=>k+"="+v).join("\n");
  const secret=crypto.createHmac("sha256","WebAppData").update(BOT_TOKEN).digest();
  const expected=crypto.createHmac("sha256",secret).update(check).digest("hex");
  if(hash.length!==expected.length||!crypto.timingSafeEqual(Buffer.from(hash),Buffer.from(expected)))return null;
  return JSON.parse(p.get("user")||"null");
 }catch{return null}
}
async function saveUser(u,ref){
 const c=await pool.connect();
 try{await c.query("BEGIN");
  const q=await c.query(`INSERT INTO users(telegram_id,first_name,username,language,referred_by) VALUES($1,$2,$3,$4,$5)
  ON CONFLICT(telegram_id) DO UPDATE SET first_name=EXCLUDED.first_name,username=EXCLUDED.username,last_seen=NOW() RETURNING (xmax=0) is_new`,
  [u.id,u.first_name,u.username||null,["uz","ru","en"].includes(u.language_code)?u.language_code:"uz",ref||null]);
  if(q.rows[0]?.is_new&&ref&&ref!==u.id){
   const exists=await c.query("SELECT 1 FROM users WHERE telegram_id=$1",[ref]);
   if(exists.rowCount){const r=await c.query("INSERT INTO referrals(referrer_id,referred_id,reward) VALUES($1,$2,$3) ON CONFLICT DO NOTHING RETURNING id",[ref,u.id,REF_REWARD]);if(r.rowCount)await c.query("UPDATE users SET balance=balance+$1 WHERE telegram_id=$2",[REF_REWARD,ref]);}
  }
  await c.query("COMMIT");
 }catch(e){await c.query("ROLLBACK");throw e}finally{c.release()}
}
async function auth(req,res,next){const u=validInit(String(req.headers["x-telegram-init-data"]||""));if(!u)return res.status(401).json({error:"Open the Mini App inside Telegram"});req.tg=u;await saveUser(u);next()}
async function isAdmin(id){return (await pool.query("SELECT 1 FROM admins WHERE telegram_id=$1",[id])).rowCount===1}
async function adminOnly(req,res,next){if(await isAdmin(req.tg.id))return next();res.status(403).json({error:"Admin access required"})}
async function tellAdmins(text,extra){const {rows}=await pool.query("SELECT telegram_id FROM admins");await Promise.allSettled(rows.map(x=>bot.telegram.sendMessage(String(x.telegram_id),text,extra)))}
function appButtons(){return Markup.inlineKeyboard([[Markup.button.webApp("🚀 Marketni ochish",PUBLIC_URL||"https://t.me")],[Markup.button.url("💬 Support","https://t.me/"+SUPPORT)]])}
function priceFor(type,quantity,plan,item){if(type==="stars")return Math.round(quantity*PRICES.star);if(type==="premium"&&["3","6","12"].includes(plan))return PRICES["premium"+plan];if(type==="gift"&&["bear","rose","rocket","diamond"].includes(item))return PRICES["gift"+item[0].toUpperCase()+item.slice(1)];if(type==="nft")return PRICES.nftBase;return 0}

bot.start(async ctx=>{const p=ctx.startPayload||"",ref=p.startsWith("ref_")?Number(p.slice(4)):null;await saveUser(ctx.from,ref);await ctx.reply(`Salom, ${ctx.from.first_name}! ✨\n\nStars, Telegram Premium va Gifts — tez va ishonchli market. Pastdagi tugma orqali kiring.`,appButtons())});
bot.command("app",ctx=>ctx.reply("Market tayyor 👇",appButtons()));
bot.command("support",ctx=>ctx.reply("Support: @"+SUPPORT,Markup.inlineKeyboard([[Markup.button.url("Yozish","https://t.me/"+SUPPORT)]])));
bot.command("admin",async ctx=>{if(!await isAdmin(ctx.from.id))return;const q=await pool.query("SELECT (SELECT COUNT(*) FROM users) users,(SELECT COUNT(*) FROM orders) orders,(SELECT COUNT(*) FROM orders WHERE status='new') new_orders");await ctx.reply(`🛡 Admin\n👥 Users: ${q.rows[0].users}\n📦 Orders: ${q.rows[0].orders}\n🔔 New: ${q.rows[0].new_orders}`,appButtons())});
bot.command("addadmin",async ctx=>{if(!await isAdmin(ctx.from.id))return;const id=Number(ctx.message.text.split(/\s+/)[1]);if(!id)return ctx.reply("Format: /addadmin 123456789");await pool.query("INSERT INTO admins(telegram_id,added_by) VALUES($1,$2) ON CONFLICT DO NOTHING",[id,ctx.from.id]);ctx.reply("✅ Admin qo‘shildi: "+id)});
bot.command("deladmin",async ctx=>{if(!await isAdmin(ctx.from.id))return;const id=Number(ctx.message.text.split(/\s+/)[1]);if(!id||ROOT_ADMINS.includes(id))return ctx.reply("ID noto‘g‘ri yoki asosiy admin.");await pool.query("DELETE FROM admins WHERE telegram_id=$1",[id]);ctx.reply("✅ Admin o‘chirildi: "+id)});
bot.action(/^o_(accepted|cancelled)_(\d+)$/,async ctx=>{if(!await isAdmin(ctx.from.id))return ctx.answerCbQuery("Ruxsat yo‘q");const q=await pool.query("UPDATE orders SET status=$1,updated_at=NOW() WHERE id=$2 RETURNING *",[ctx.match[1],ctx.match[2]]);if(q.rowCount)await bot.telegram.sendMessage(String(q.rows[0].telegram_id),`📦 Buyurtma #${q.rows[0].id}: ${ctx.match[1]}`);await ctx.editMessageReplyMarkup(undefined);ctx.answerCbQuery("Yangilandi")});

app.use(bot.webhookCallback("/telegram/webhook",{secretToken:WEBHOOK_SECRET}));
app.get("/health",(_q,res)=>res.json({ok:true}));
app.get("/api/config",(_q,res)=>res.json({support:SUPPORT,cardNumber:CARD_NUMBER,cardHolder:CARD_HOLDER,referralReward:REF_REWARD,prices:PRICES}));
app.get("/api/me",auth,async(req,res)=>{const [u,r,a]=await Promise.all([pool.query("SELECT telegram_id,first_name,username,language,theme,balance FROM users WHERE telegram_id=$1",[req.tg.id]),pool.query("SELECT COUNT(*)::int count,COALESCE(SUM(reward),0) total FROM referrals WHERE referrer_id=$1",[req.tg.id]),isAdmin(req.tg.id)]);res.json({...u.rows[0],referrals:r.rows[0],isAdmin:a,botUsername:bot.botInfo?.username||""})});
app.patch("/api/settings",auth,async(req,res)=>{const l=["uz","ru","en"].includes(req.body.language)?req.body.language:null,t=["light","dark","system"].includes(req.body.theme)?req.body.theme:null;if(!l&&!t)return res.status(400).json({error:"Invalid setting"});await pool.query("UPDATE users SET language=COALESCE($1,language),theme=COALESCE($2,theme) WHERE telegram_id=$3",[l,t,req.tg.id]);res.json({ok:true})});
app.get("/api/orders",auth,async(req,res)=>res.json((await pool.query("SELECT * FROM orders WHERE telegram_id=$1 ORDER BY created_at DESC LIMIT 50",[req.tg.id])).rows));
app.post("/api/orders",auth,async(req,res)=>{
 const type=String(req.body.type||""),quantity=Number(req.body.quantity||1),plan=String(req.body.plan||""),item=String(req.body.item||""),recipient=String(req.body.recipient||"").trim().slice(0,100),note=String(req.body.note||"").trim().slice(0,500);
 if(!["stars","premium","gift","nft"].includes(type)||!recipient||!Number.isFinite(quantity)||quantity<=0||quantity>100000)return res.status(400).json({error:"Ma’lumotlar noto‘g‘ri"});
 const price=priceFor(type,quantity,plan,item);if(!price)return res.status(400).json({error:"Noto‘g‘ri mahsulot"});
 const giftNames={bear:"Mishka Gift",rose:"Atirgul Gift",rocket:"Raketa Gift",diamond:"Olmos Gift"};const name=type==="stars"?quantity+" Telegram Stars":type==="premium"?"Telegram Premium "+plan+" oy":type==="nft"?"NFT/NFC Gift buyurtmasi":giftNames[item];
 const q=await pool.query("INSERT INTO orders(telegram_id,product_type,product_name,quantity,price,recipient,note) VALUES($1,$2,$3,$4,$5,$6,$7) RETURNING *",[req.tg.id,type,name,quantity,price,recipient,note]);
 const o=q.rows[0],un=req.tg.username?"@"+req.tg.username:"username yo‘q";
 await tellAdmins(`🔥 YANGI BUYURTMA #${o.id}\n\n👤 ${req.tg.first_name} (${un})\n🆔 ${req.tg.id}\n📦 ${o.product_name}\n💰 ${Number(o.price).toLocaleString()} UZS\n🎯 ${recipient}\n📝 ${note||"—"}`,Markup.inlineKeyboard([[Markup.button.callback("✅ Qabul","o_accepted_"+o.id),Markup.button.callback("❌ Bekor","o_cancelled_"+o.id)]]));
 res.status(201).json(o);
});
app.get("/api/admin/stats",auth,adminOnly,async(_q,res)=>res.json((await pool.query("SELECT (SELECT COUNT(*)::int FROM users) users,(SELECT COUNT(*)::int FROM orders) orders,(SELECT COUNT(*)::int FROM orders WHERE status='new') new_orders,(SELECT COUNT(*)::int FROM referrals) referrals,(SELECT COALESCE(SUM(price),0) FROM orders WHERE status='completed') revenue")).rows[0]));
app.get("/api/admin/orders",auth,adminOnly,async(_q,res)=>res.json((await pool.query("SELECT o.*,u.first_name,u.username FROM orders o LEFT JOIN users u ON u.telegram_id=o.telegram_id ORDER BY o.created_at DESC LIMIT 200")).rows));
app.patch("/api/admin/orders/:id",auth,adminOnly,async(req,res)=>{const s=["new","accepted","paid","completed","cancelled"].includes(req.body.status)?req.body.status:null;if(!s)return res.status(400).json({error:"Invalid status"});const q=await pool.query("UPDATE orders SET status=$1,updated_at=NOW() WHERE id=$2 RETURNING *",[s,req.params.id]);if(!q.rowCount)return res.status(404).json({error:"Not found"});await bot.telegram.sendMessage(String(q.rows[0].telegram_id),`📦 Buyurtma #${q.rows[0].id}: ${s}`);res.json(q.rows[0])});
app.get("/api/admin/admins",auth,adminOnly,async(_q,res)=>res.json((await pool.query("SELECT * FROM admins ORDER BY created_at")).rows));
app.post("/api/admin/admins",auth,adminOnly,async(req,res)=>{const id=Number(req.body.telegramId);if(!id)return res.status(400).json({error:"Invalid ID"});await pool.query("INSERT INTO admins(telegram_id,added_by) VALUES($1,$2) ON CONFLICT DO NOTHING",[id,req.tg.id]);res.json({ok:true})});
app.delete("/api/admin/admins/:id",auth,adminOnly,async(req,res)=>{const id=Number(req.params.id);if(ROOT_ADMINS.includes(id))return res.status(400).json({error:"Root admin"});await pool.query("DELETE FROM admins WHERE telegram_id=$1",[id]);res.json({ok:true})});
app.get("*",(_q,res)=>res.sendFile(path.join(__dirname,"public","index.html")));
app.use((e,_q,res,_n)=>{console.error(e);res.status(500).json({error:"Server xatosi"})});

async function main(){await dbInit();bot.botInfo=await bot.telegram.getMe();if(PUBLIC_URL){await bot.telegram.setChatMenuButton({menuButton:{type:"web_app",text:"Market",web_app:{url:PUBLIC_URL}}});await bot.telegram.setMyCommands([{command:"start",description:"Botni ishga tushirish"},{command:"app",description:"Marketni ochish"},{command:"support",description:"Support"}])}app.listen(Number(env.PORT||3000),"0.0.0.0",()=>console.log("Server ready"));if(PUBLIC_URL){await bot.telegram.setWebhook(PUBLIC_URL+"/telegram/webhook",{secret_token:WEBHOOK_SECRET});console.log("Telegram webhook ready")}else{await bot.launch()}}
main().catch(e=>{console.error(e);process.exit(1)});
process.once("SIGINT",()=>bot.stop("SIGINT"));process.once("SIGTERM",()=>bot.stop("SIGTERM"));
