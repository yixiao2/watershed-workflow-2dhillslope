Yi:
I was checking those ELM simulation files under `/pscratch/sd/l/lizh142/elm`. There are five subfolders, could you briefly explain the case for each folder?
My guess is
1.folder `ELM_MOSART_CONUS.2024-07-14-142526`: This is the largest one (1.3T). Each file is a one-year ELM simulation? from 1981/1/1 to sometime in 2024?
2.folder `ELM_MOSART_CONUS.2024-08-27-132724`: It has two files corresponding to two specific days? for some comparison between pre-fire and post-fire ELM simulations?
3.folder `ELM_MOSART_CONUS.2024-08-27-150810`: looks like post-fire simulations from 2021/08/09 to 2024/01/02.
4.folder `ELM_MOSART_CONUS.2024-11-20-210107`: another post-fire simulations. The time range is same as folder 3
5.folder `ELM_MOSART_CONUS.2024-11-20-220109`: again another post-fire simulations
I guess for folder 3/4/5, I'd like know what's the difference. Thanks!


Zhi:
1.Long term no fire run. Ok to use.
2.Ignition day run. Typically no need to use this.
3.Post-fire run. Don't use it because it's corrected by (4).
4.Corrected post-fire run. Ok to use.
5.Corrected post-fire run but without fire. Ok to use.

pre-fire: use (1); post-fire: use (4) and (5)